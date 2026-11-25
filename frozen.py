"""Frozen screens (1E): ad breaks, "be right back" slates, loading or paused screens.

A clip taken from there is worthless, so before a clip is rendered its own range is checked: mean luma difference between
consecutive frames (ffmpeg tblend=difference + signalstats). PeakCut measured about 0.19 on an ad slate and 1.6-2.5 on gameplay,
so a flat threshold separates them without OCR or a model. Only the clip's range is decoded (small and sampled), so it costs about
a second per clip, in Fast mode too.

Adapted from PeakCut's studio/quality.py, MIT License, Copyright (c) 2026 PeakCut contributors.
"""
import re
import subprocess

THRESHOLD = 0.4          # PeakCut's default: below this the picture is not really moving
DROP_SHARE = 0.6         # a clip that is frozen for more than 60% of its length is dropped
_PTS = re.compile(r'pts_time:([0-9.]+)')
_YAVG = re.compile(r'lavfi\.signalstats\.YAVG=([0-9.]+)')


def motion(path, start=0.0, length=None, fps=6, width=320):
    """[(seconds from start, luma difference)] for the range, or [] if it cannot be read."""
    cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-ss', f'{max(0.0, start):.2f}']
    if length:
        cmd += ['-t', f'{length:.2f}']
    cmd += ['-i', str(path), '-an', '-vf', f'fps={fps},scale={width}:-2,tblend=all_mode=difference,signalstats,metadata=print:file=-',
            '-f', 'null', '-']
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except Exception:      # noqa: BLE001 - a missing ffmpeg or a timeout must never stop a job
        return []
    out, at = [], 0.0
    for line in (proc.stdout or '').splitlines():
        m = _PTS.search(line)
        if m:
            at = float(m.group(1))
            continue
        m = _YAVG.search(line)
        if m:
            out.append((at, float(m.group(1))))
    return out[1:] if len(out) > 1 else []        # the first blended frame is against black


def frozen_share(path, start=0.0, length=None):
    """Share (0..1) of the range where the picture stands still, or None when it could not be measured."""
    rows = motion(path, start, length)
    if len(rows) < 6:
        return None
    still = sum(1 for _, v in rows if v < THRESHOLD)
    return still / len(rows)


def is_frozen(path, start=0.0, length=None):
    share = frozen_share(path, start, length)
    return share is not None and share > DROP_SHARE, share
