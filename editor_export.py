"""Export the saved gameplay and facecam as separate FCP 7 XML tracks."""

import math
import re
import shutil
import subprocess
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from fastapi import HTTPException
from fastapi.responses import FileResponse, Response

import camfx
import encoders
import layouts
import styling
from reedit import latest_file, read_record


def node(parent, tag, value=None, **attrs):
    child = ET.SubElement(parent, tag, attrs)
    if value is not None:
        child.text = str(value)
    return child


def rate(parent, fps):
    item = node(parent, "rate")
    node(item, "timebase", fps)
    node(item, "ntsc", "FALSE")


def video_format(parent, width, height, fps):
    sample = node(parent, "samplecharacteristics")
    rate(sample, fps)
    node(sample, "width", width)
    node(sample, "height", height)
    node(sample, "anamorphic", "FALSE")
    node(sample, "pixelaspectratio", "square")
    node(sample, "fielddominance", "none")


def interchange(folder, title, width, height, fps, frames, with_audio):
    root = ET.Element("xmeml", version="5")
    sequence = node(root, "sequence", id="bloom-timeline")
    node(sequence, "name", title)
    node(sequence, "duration", frames)
    rate(sequence, fps)
    media = node(sequence, "media")
    video = node(media, "video")
    video_format(node(video, "format"), width, height, fps)
    for idx, name in enumerate(("Gameplay.mp4", "Facecam.mov"), 1):
        track = node(video, "track")
        clip = node(track, "clipitem", id=f"video-{idx}")
        node(clip, "name", Path(name).stem)
        node(clip, "enabled", "TRUE")
        rate(clip, fps)
        for tag, value in (("start", 0), ("end", frames), ("in", 0), ("out", frames), ("duration", frames)):
            node(clip, tag, value)
        source = node(clip, "file", id=f"source-{idx}")
        node(source, "name", name)
        node(source, "pathurl", (folder / name).resolve().as_uri())
        rate(source, fps)
        node(source, "duration", frames)
        streams = node(source, "media")
        video_format(node(streams, "video"), width, height, fps)
        if idx == 1 and with_audio:
            sound = node(streams, "audio")
            node(sound, "channelcount", 2)
            params = node(sound, "samplecharacteristics")
            node(params, "depth", 16)
            node(params, "samplerate", 48000)
    if with_audio:
        audio = node(media, "audio")
        for channel in (1, 2):
            clip = node(node(audio, "track"), "clipitem", id=f"audio-{channel}")
            node(clip, "name", "Gameplay audio")
            node(clip, "enabled", "TRUE")
            rate(clip, fps)
            for tag, value in (("start", 0), ("end", frames), ("in", 0), ("out", frames), ("duration", frames)):
                node(clip, tag, value)
            node(clip, "file", id="source-1")
            source_track = node(clip, "sourcetrack")
            node(source_track, "mediatype", "audio")
            node(source_track, "trackindex", channel)
    return '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n' + ET.tostring(root, encoding="unicode")


def filter_layer(box, layer, source, canvas, fps, face_look=""):
    x0 = max(0, min(source["w"] - 2, int(box["x"] * source["w"])))
    y0 = max(0, min(source["h"] - 2, int(box["y"] * source["h"])))
    crop_w = max(2, min(source["w"] - x0, int(box["w"] * source["w"])))
    crop_h = max(2, min(source["h"] - y0, int(box["h"] * source["h"])))
    width, height = canvas
    w, h = layer["w"], layer["h"]
    view = (
        f"crop={crop_w}:{crop_h}:{x0}:{y0},"
        f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h},"
        f"setsar=1,fps={fps}{face_look}"
    )
    is_camera = layer["source"] == "cam"
    if layer.get("circle"):
        view += ",format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='if(lte(hypot(X-W/2,Y-H/2),min(W,H)/2),255,0)'"
    if is_camera:
        view += ",format=yuva444p10le"
    color = "black@0" if is_camera else "black"
    return view + f",pad={width}:{height}:{layer['x']}:{layer['y']}:{color}"


def build(data, file, folder, probe):
    file = latest_file(data, file)
    record = read_record(data, file)
    settings = record["settings"]
    source_id = str(record.get("source", ""))
    source = data / (source_id + ".mp4")
    if not source_id.isalnum() or not source.is_file():
        raise HTTPException(409, "The saved source is unavailable.")
    width, height, requested_fps = layouts.output_settings(settings)
    layers = layouts.geometry(settings.get("layout", "blur"), settings.get("top", .32), width, height)["layers"]
    camera = next((row for row in layers if row["source"] == "cam"), None)
    game = next((row for row in layers if row["source"] == "game"), None)
    if camera is None or game is None:
        raise HTTPException(400, "Choose and export a layout with separate facecam and gameplay first.")
    title = str(settings.get("title") or "BloomClipping edit")
    meta = probe(source)
    start = float(settings.get("start", 0))
    duration = min(float(settings.get("end", 0)), meta["duration"]) - start
    if not 0 < duration <= 600:
        raise HTTPException(400, "The saved clip has an invalid source range.")
    source_fps, audio = styling.source_info(source)
    fps = requested_fps or min((24, 25, 30, 50, 60), key=lambda value: abs(value - source_fps))
    frames = max(1, round(duration * fps))
    folder.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(folder).free < max(128 * 1024**2, int(width * height * fps * duration)):
        raise HTTPException(507, "Free up storage for the separate editing tracks.")
    token = uuid.uuid4().hex
    output = folder / token
    output.mkdir()
    archive = folder / (token + ".zip")
    base = ["ffmpeg", "-nostdin", "-y", "-v", "error", "-ss", str(start), "-i", str(source), "-t", str(duration)]
    try:
        game_filter = filter_layer(settings["game"], game, meta, (width, height), fps)
        clip_audio = ["-map", "0:a:0", "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "48000"] if audio else ["-an"]
        for encoder in encoders.h264(cq=19, x264_preset="fast", nv_preset="p5"):
            result = subprocess.run([*base, "-map", "0:v:0", "-vf", game_filter, *clip_audio,
                                     *encoder, "-pix_fmt", "yuv420p", str(output / "Gameplay.mp4")],
                                    capture_output=True, timeout=1200)
            if not result.returncode:
                break
        if result.returncode:
            raise RuntimeError("Gameplay encoding failed.")
        face_filter = filter_layer(settings["cam"], camera, meta, (width, height), fps, camfx.filter(settings))
        subprocess.run([*base, "-map", "0:v:0", "-vf", face_filter, "-an", "-c:v", "prores_ks", "-profile:v", "4",
                        "-pix_fmt", "yuva444p10le", str(output / "Facecam.mov")],
                       capture_output=True, timeout=1200, check=True)
        (output / "BloomClipping.xml").write_text(interchange(output, title, width, height, fps, frames, audio), encoding="utf-8")
        srt = data / (file + ".srt")
        if srt.is_file() and record["result"].get("caption_words"):
            shutil.copyfile(srt, output / "Captions.srt")
        (output / "Import.txt").write_text(
            "Extract the ZIP. Import BloomClipping.xml into Premiere Pro or DaVinci Resolve. "
            "If the app asks for media, relink Gameplay.mp4 and Facecam.mov from the extracted folder. "
            "Import Captions.srt separately when included. The Facecam track has transparency and can be moved independently.\n",
            encoding="utf-8",
        )
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as handle:
            for asset in output.iterdir():
                handle.write(asset, asset.name)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, RuntimeError) as exc:
        archive.unlink(missing_ok=True)
        shutil.rmtree(output, ignore_errors=True)
        raise HTTPException(500, "Could not prepare the editing tracks.") from exc
    return {"download": "/editor-export/" + token}


def attach(app, data, probe):
    folder = data / "editor-exports"

    @app.post("/editor-export")
    def export_editor_project(body: dict):
        file = body.get("file", "")
        if not isinstance(file, str) or not re.fullmatch(r"[a-zA-Z0-9]{1,64}", file):
            raise HTTPException(400, "Choose a saved clip.")
        return build(data, file, folder, probe)

    @app.get("/editor-export/{token}")
    def download_editor_project(token: str):
        if not re.fullmatch(r"[a-f0-9]{32}", token):
            raise HTTPException(404)
        archive = folder / (token + ".zip")
        if not archive.is_file():
            raise HTTPException(404, "This editing export is unavailable.")
        return FileResponse(archive, filename="BloomClipping-editing-tracks.zip", media_type="application/zip")

    @app.get("/reaction-gif/{file}")
    def download_reaction(file: str, at: float = 0):
        if not re.fullmatch(r"[a-zA-Z0-9]{1,64}", file) or not math.isfinite(at):
            raise HTTPException(400, "Choose a saved clip and a valid time.")
        clip = data / (latest_file(data, file) + ".mp4")
        if not clip.is_file():
            raise HTTPException(404, "The saved clip is unavailable.")
        duration = probe(clip)["duration"]
        start = max(0, min(at - 1.25, duration - 2.5))
        command = ["ffmpeg", "-nostdin", "-v", "error", "-ss", str(start), "-t", "2.5", "-i", str(clip),
                   "-an", "-vf", "fps=12,scale=320:-2:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse",
                   "-loop", "0", "-f", "gif", "-"]
        try:
            result = subprocess.run(command, capture_output=True, timeout=30, check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            raise HTTPException(500, "Could not make the reaction GIF.") from exc
        return Response(result.stdout, media_type="image/gif",
                        headers={"Content-Disposition": 'attachment; filename="BloomClipping-reaction.gif"'})
