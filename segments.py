"""Cut a clip from several pieces of the saved video (split, drop, reorder, duplicate in the Editor).

Idea taken from OpenCut's timeline: every piece is "a range of the source", a split makes two pieces, and the edit is the ordered list of pieces.
The pieces are joined into one derived source file; the normal export then runs on it like on any other video.
"""
import hashlib
import json
import math
import subprocess

MAX_PIECES = 16


def validate(segs, duration):
    """List of (start, end) floats, or ValueError."""
    if not isinstance(segs, list) or not 1 <= len(segs) <= MAX_PIECES:
        raise ValueError(f'Use between 1 and {MAX_PIECES} pieces.')
    out = []
    for s in segs:
        try:
            a, b = float(s['start']), float(s['end'])
        except (KeyError, TypeError, ValueError):
            raise ValueError('Each piece needs a start and an end.')
        if not (math.isfinite(a) and math.isfinite(b)) or a < 0 or b - a < .2 or b > duration + .05:
            raise ValueError('A piece must be at least 0.2 s long and inside the saved video.')
        out.append((round(a, 3), round(min(b, duration), 3)))
    total = sum(b - a for a, b in out)
    if not 3 <= total <= 180:
        raise ValueError('The clip must be 3 to 180 seconds long in total.')
    return out


def derived_id(origin, pieces):
    return 'sg' + hashlib.sha1((origin + json.dumps(pieces)).encode()).hexdigest()[:20]


def has_audio(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0', str(path)], capture_output=True, text=True)
    return bool(r.stdout.strip())


def graph(pieces, audio):
    parts, labels = [], ''
    for i, (a, b) in enumerate(pieces):
        parts.append(f'[0:v]trim={a}:{b},setpts=PTS-STARTPTS[v{i}]')
        if audio:
            parts.append(f'[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS[a{i}]')
        labels += f'[v{i}][a{i}]' if audio else f'[v{i}]'
    parts.append(f'{labels}concat=n={len(pieces)}:v=1:a={1 if audio else 0}' + ('[v][a]' if audio else '[v]'))
    return ';'.join(parts)


def build(data, origin, pieces):
    """Make (once) the joined file for these pieces; returns its id. Same pieces -> same file."""
    sid = derived_id(origin, pieces)
    out = data / (sid + '.mp4')
    if out.exists():
        return sid
    src = data / (origin + '.mp4')
    audio = has_audio(src)
    tmp = data / (sid + '.part.mp4')
    cmd = ['ffmpeg', '-y', '-v', 'error', '-i', str(src), '-filter_complex', graph(pieces, audio), '-map', '[v]'] + (['-map', '[a]', '-c:a', 'aac', '-b:a', '192k'] if audio else ['-an']) + \
          ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '17', '-movflags', '+faststart', str(tmp)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        raise RuntimeError('Joining the pieces failed: ' + (r.stderr or '')[-300:])
    tmp.replace(out)
    return sid
