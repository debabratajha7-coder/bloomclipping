"""YouTube "Most replayed" (3D): the hill graph above YouTube's progress bar, as a per-second signal.

yt-dlp already returns it with the video info (`heatmap`: about 100 segments, value 0..1) for popular videos; nothing extra is
downloaded. Every video looks hot at its very start (everyone starts there) and drifts down after, so the curve is compared with
its own local level and the opening is ignored, the way Clips Kitty's hype.py detrends a retention curve (idea only).
Smaller or new videos have no heatmap: then this returns None and nothing changes.
"""
import numpy as np


def from_info(info):
    rows = (info or {}).get('heatmap') or []
    out = []
    for r in rows:
        try:
            a, b, v = float(r['start_time']), float(r['end_time']), float(r['value'])
        except (KeyError, TypeError, ValueError):
            continue
        if b > a and np.isfinite(v):
            out.append([round(a, 2), round(b, 2), round(max(0.0, min(1.0, v)), 4)])
    return out if len(out) >= 10 else None


def per_second(heat, duration):
    """0..1 per second: how much more this second was replayed than the video around it. None without data."""
    if not heat or not duration or duration < 30:
        return None
    n = int(np.ceil(duration))
    raw = np.zeros(n)
    for a, b, v in heat:
        raw[int(a):max(int(a) + 1, int(np.ceil(b)))] = v
    win = max(5, n // 8) | 1
    pad = np.pad(raw, win // 2, mode='edge')
    base = np.array([np.median(pad[i:i + win]) for i in range(n)])
    lift = np.clip(raw - base, 0, None)
    lift[:max(5, int(n * .04))] = 0                      # the opening is always "replayed": not a moment
    top = float(np.percentile(lift[lift > 0], 95)) if (lift > 0).any() else 0
    if top <= 0:
        return None
    return np.clip(lift / top, 0, 1)


def window(signal, start, end):
    if signal is None:
        return None
    a, b = int(max(0, start)), int(max(start + 1, end))
    part = signal[a:b]
    return float(part.max()) if len(part) else None
