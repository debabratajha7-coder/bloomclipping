"""Opt-in word censorship and progress graphics for saved exports."""

import math
import unicodedata

KEYS = ("censor_mode", "censor_words", "clip_progress", "loop_end", "effect_cues")
MODES = ("off", "mute", "bleep", "bar", "blur")
CUE_TYPES = ("hit", "sweep", "flash")


def normalize(word):
    text = word.strip().casefold()
    while text and unicodedata.category(text[0])[0] in "PS":
        text = text[1:]
    while text and unicodedata.category(text[-1])[0] in "PS":
        text = text[:-1]
    return text


def settings(body):
    mode = body.get("censor_mode") or "off"
    if mode not in MODES:
        raise ValueError("Choose a supported word censorship effect.")
    raw = body.get("censor_words") or ""
    if not isinstance(raw, str) or len(raw) > 1000:
        raise ValueError("Enter at most 1,000 characters of words to censor.")
    words = {normalize(value) for value in raw.replace(",", " ").split()} - {""}
    return mode, words


def cues(body, duration):
    values = body.get("effect_cues") or []
    if not isinstance(values, list) or len(values) > 16:
        raise ValueError("Choose up to 16 effects on this clip.")
    results = []
    for value in values:
        if not isinstance(value, dict) or value.get("kind") not in CUE_TYPES:
            raise ValueError("Choose a supported action from the editor.")
        at = value.get("at")
        if type(at) not in (int, float) or not math.isfinite(at) or not 0 <= at < duration:
            raise ValueError("Effects must be placed inside this clip.")
        results.append((value["kind"], at))
    return results


def masked_words(words, picked, duration):
    output, spans = [], []
    for word in words:
        if normalize(word["text"]) in picked:
            start, end = max(0, word["start"] - .035), min(duration, word["end"] + .045)
            if end > start:
                if spans and start <= spans[-1][1] + .02:
                    spans[-1] = spans[-1][0], max(end, spans[-1][1])
                else:
                    spans.append((start, end))
            output.append({**word, "text": "****"})
        else:
            output.append(word)
    return output, spans


def enable(spans):
    return "+".join(f"between(t,{start:.3f},{end:.3f})" for start, end in spans)


def audio_filter(spans, duration, mode, source="[0:a]"):
    event = enable(spans)
    mute = f"{source}asetpts=PTS-STARTPTS,volume=0:enable='{event}'"
    if mode != "bleep":
        return mute + "[censored]"
    tone = f"sine=f=1000:r=48000:d={duration:.3f},volume='if({event},0.6,0)':eval=frame[tone]"
    return mute + "[quiet];" + tone + ";[quiet][tone]amix=inputs=2:duration=first:normalize=0[censored]"


def video_filter(mode, spans, camera):
    if not spans or not camera or mode not in ("bar", "blur"):
        return ""
    event = enable(spans)
    x, y, w, h = (camera[key] for key in ("x", "y", "w", "h"))
    if mode == "bar":
        return f"[effect_input]drawbox=x={x+w//5}:y={y+h*3//5}:w={w*3//5}:h={max(2,h//6)}:color=black:t=fill:enable='{event}'[base]"
    strength = max(1, min(12, w // 20, h // 20))
    return (f"[effect_input]split[base_clear][cam_copy];[cam_copy]crop={w}:{h}:{x}:{y},"
            f"boxblur={strength}:2[cam_blur];[base_clear][cam_blur]overlay={x}:{y}:enable='{event}'[base]")


def progress_filter(width, height, duration, fps):
    bar = max(4, (height // 120) // 2 * 2)
    return (f"color=c=0xFF4BA5:s={width}x{bar}:r={fps or 30}:d={duration:.3f}[strip];"
            f"[effect_input][strip]overlay=x='main_w*min(1,max(0,t/{duration:.4f}))-overlay_w':"
            f"y=main_h-overlay_h:eval=frame:shortest=1[base]")


def loop_filter(duration, fps):
    fade = min(.30, duration / 4)
    at = duration - fade
    return (
        "[effect_input]split[loop_video][first_frame];"
        f"[first_frame]trim=end_frame=1,setpts=PTS-STARTPTS,fps={fps or 30},"
        f"tpad=stop_mode=clone:stop_duration={fade+.1:.3f},format=yuva420p,"
        f"fade=t=in:st=0:d={fade:.3f}:alpha=1,setpts=PTS+{at:.3f}/TB[loop_head];"
        f"[loop_video][loop_head]overlay=enable='gte(t,{at:.3f})':eof_action=repeat[base]"
    )


def timed_flash(values):
    spans = [(at, at+.12) for kind,at in values if kind == "flash"]
    if not spans:return ""
    return f"[effect_input]drawbox=x=0:y=0:w=iw:h=ih:color=white@0.27:t=fill:enable='{enable(spans)}'[base]"


def timed_audio(values, duration, source, has_audio):
    sounds = [(kind,at) for kind,at in values if kind in ("hit","sweep")]
    if not sounds:return ""
    filters = []
    active = [source]
    if not has_audio:
        filters.append(f"anullsrc=r=48000:cl=stereo:d={duration:.3f}[room]")
        active = ["[room]"]
    for index,(kind,at) in enumerate(sounds):
        ms=round(1000*at)
        label=f"[cue{index}]"
        if kind=="hit":
            piece="sine=f=92:r=48000:d=0.23,volume=1.5,afade=t=out:st=0.03:d=0.20"
        else:
            piece="aevalsrc=0.15*sin(2*PI*(190*t+950*t*t)):s=48000:d=0.27,afade=t=in:d=0.04,afade=t=out:st=0.13:d=0.14"
        filters.append(f"{piece},adelay={ms}:all=1{label}")
        active.append(label)
    filters.append("".join(active)+f"amix=inputs={len(active)}:duration=first:normalize=0,alimiter=limit=0.96:latency=1[editor_mix]")
    return ";".join(filters)
