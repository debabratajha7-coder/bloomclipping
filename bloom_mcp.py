# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.12,<2"]
# ///
"""Local stdio MCP connector. Run with uv run --script bloom_mcp.py."""
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from mcp.server.fastmcp import FastMCP

server = FastMCP("BloomClipping")
port = int(os.environ.get("BLOOMCLIPPING_PORT", "8770"))
base = f"http://127.0.0.1:{port}"


def identifier(value: str) -> str:
    if not re.fullmatch(r"[a-f0-9]{32}", value):
        raise ValueError("Expected a BloomClipping job or clip ID.")
    return value


def api(path: str, body=None):
    request = Request(base + path, data=None if body is None else json.dumps(body).encode(),
                      headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        raise ValueError(error.read(2048).decode(errors="replace")) from error
    except URLError as error:
        raise RuntimeError(f"Start the BloomClipping app on port {port}.") from error


@server.tool()
def create_clips(source: str, count: int = 3, focus: str = "") -> dict:
    """Start a local batch from a supported video URL or an existing uploaded source ID."""
    if not 1 <= count <= 12:
        raise ValueError("Choose between 1 and 12 clips.")
    source = source.strip()
    origin = {"url": source} if source.startswith(("https://", "http://")) else {"id": identifier(source)}
    return api("/make", {**origin, "count": count, "focus_brief": focus})


@server.tool()
def batch_status(job: str) -> dict:
    """Get the current processing stage, progress, and available clips."""
    return api("/make/" + identifier(job))


@server.tool()
def resume_batch(job: str) -> dict:
    """Resume an interrupted batch from its saved analysis."""
    return api("/make/" + identifier(job) + "/resume", {})


@server.tool()
def list_clips(limit: int = 20, offset: int = 0) -> list:
    """List saved exports, newest first, with their local media links."""
    if offset < 0 or not 1 <= limit <= 100:
        raise ValueError("Use a nonnegative offset and a limit from 1 to 100.")
    return [{"id": row["id"], "title": row.get("title"), "meta": row.get("meta"),
             "url": base + "/media/" + row["id"]} for row in api("/library")[offset:offset+limit]]


@server.tool()
def export_clip(clip: str, aspect: str = "vertical", resolution: int = 1080) -> dict:
    """Render a new MP4 from a saved clip. Poll batch_status using the returned job ID."""
    if aspect not in {"vertical","square","landscape"} or resolution not in {720,1080}:
        raise ValueError("Choose vertical, square or landscape output in 720p or 1080p.")
    edit = api("/clips/" + identifier(clip) + "/edit")
    settings = dict(edit["settings"])
    settings.update(id=edit["source"]["id"], aspect=aspect, resolution=resolution)
    return api("/export", settings)


@server.tool()
def download_clip(clip: str) -> str:
    """Save an exported library clip into Downloads/BloomClipping and return its path."""
    clip = identifier(clip)
    if not any(item["id"] == clip for item in api("/library")):
        raise ValueError("Choose an exported clip from list_clips.")
    folder = Path.home() / "Downloads" / "BloomClipping"
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=folder, delete=False) as temp:
        staged = Path(temp.name)
    try:
        with urlopen(base + "/media/" + clip, timeout=60) as response, staged.open("wb") as output:
            shutil.copyfileobj(response, output)
        target = folder / (clip + ".mp4")
        staged.replace(target)
        return str(target)
    finally:
        staged.unlink(missing_ok=True)


if __name__ == "__main__":
    server.run(transport="stdio")
