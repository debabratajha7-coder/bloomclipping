"""Find hard cuts in short windows around a clip without cutting into speech."""

import re
import subprocess

SCENE_PTS = re.compile(r"pts_time:(\d+(?:\.\d+)?)")


def hard_cuts(media, start, end):
    origin = max(0, start - .18)
    if end <= start:
        return []
    command = [
        "ffmpeg", "-nostdin", "-hide_banner", "-ss", f"{origin:.3f}", "-t", f"{end - origin:.3f}",
        "-i", str(media), "-an",
        "-vf", "scale=160:90,select='gt(scene,0.43)',showinfo", "-f", "null", "-",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode:
        return []
    cuts = [origin + float(match.group(1)) for match in SCENE_PTS.finditer(result.stderr)]
    return [value for value in cuts if start <= value <= end]


def align(media, start, end, words, minimum):
    if not words or end - start <= minimum:
        return start, end
    first_word = start + min(float(word["start"]) for word in words)
    last_word = start + max(float(word["end"]) for word in words)
    head_end = min(first_word - .045, start + 1.2, end - minimum)
    tail_start = max(last_word + .045, end - 1.2, start + minimum)
    lead = hard_cuts(media, start + .08, head_end) if head_end > start + .15 else []
    tail = hard_cuts(media, tail_start, end - .08) if tail_start < end - .15 else []
    if lead:
        start = max(lead)
    if tail:
        end = min((cut for cut in tail if cut - start >= minimum), default=end)
    return round(start, 3), round(end, 3)
