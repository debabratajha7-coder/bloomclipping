"""Storage: what fills the data folder, safe ways to free space, and choosing another data folder.

Nothing is deleted without a click on the page. Everything stays inside the data folder; files touched in the last 15 minutes and
anything while a job is running are left alone. Deleting clips cannot be undone, the other actions only remove things that can be
made again (downloads, previews, temporary audio).
"""
from pathlib import Path
import json, os, re, shutil, time

RECENT = 15 * 60
HEX = re.compile(r'^[a-f0-9]{32}$')
SKIP_JSON = ('.state.json', '.request.json', '.words.json', '.resume.json')
ACTIONS = ('temp', 'recordings', 'orphans', 'sources', 'old_clips')


def _used_sources(records):
    """Source ids that finished clips need: the file they were made from, and the original video of a clip built from several pieces."""
    used = set()
    for r in records:
        if r.get('source'):
            used.add(str(r['source']))
        origin = (r.get('settings') or {}).get('origin_id')
        if origin:
            used.add(str(origin))
    return used


def _size(path):
    path = Path(path)
    try:
        if path.is_file():
            return path.stat().st_size
        return sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
    except OSError:
        return 0


def _inside(data, path):
    try:
        Path(path).resolve().relative_to(Path(data).resolve())
        return True
    except (ValueError, OSError):
        return False


def clip_records(data):
    """{clip id: record} for finished clips (clip id = file stem of its mp4 and json)."""
    out = {}
    for f in Path(data).glob('*.json'):
        if f.name.endswith(SKIP_JSON) or not HEX.match(f.stem):
            continue
        try:
            record = json.loads(f.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if isinstance(record, dict) and isinstance(record.get('result'), dict) and record['result'].get('status') == 'done' and 'settings' in record:
            out[f.stem] = record
    return out


def clip_files(data, clip_id):
    data = Path(data)
    names = [clip_id + ext for ext in ('.mp4', '.json', '.ass', '.srt', '.vtt', '.cover.jpg')]
    return [data / n for n in names if (data / n).exists()]


def _newest(path):
    """Latest modification time of a file, or of anything inside a folder."""
    path = Path(path)
    try:
        if path.is_file():
            return path.stat().st_mtime
        times = [f.stat().st_mtime for f in path.rglob('*') if f.is_file()]
        return max(times) if times else path.stat().st_mtime
    except OSError:
        return time.time()


def _old(path, now, seconds=RECENT):
    return now - _newest(path) > seconds


def plan(data, action, days=30, now=None):
    """{'files': [paths and folders], 'bytes': n} that `action` would delete. Nothing is touched."""
    data = Path(data)
    now = now or time.time()
    clips = clip_records(data)
    files = []
    if action == 'temp':
        for f in data.rglob('*'):
            if not f.is_file():
                continue
            rel = f.relative_to(data).parts
            if rel[0] in ('models', 'bundles') and f.suffix != '.zip':
                continue
            if f.suffix in ('.part', '.ytdl') or f.name.endswith('.state.tmp'):
                if _old(f, now):
                    files.append(f)
            elif len(rel) == 1 and f.suffix in ('.m4a', '.webm', '.opus', '.wav') and _old(f, now):
                files.append(f)
            elif rel[0] == 'bundles' and f.suffix == '.zip' and _old(f, now, 3600):
                files.append(f)
        for d in data.iterdir():
            if d.is_dir() and d.name.endswith('-preview') and _old(d, now):
                files.append(d)
            elif d.is_dir() and HEX.match(d.name) and _old(d, now):
                if not any(f.suffix == '.mp4' and f.stat().st_size > 0 and not f.name.endswith('.part') for f in d.rglob('*') if f.is_file()):
                    files.append(d)          # a job folder with only partial downloads
        files = _dedupe(files)
    elif action == 'recordings':
        for d in data.glob('live_*'):
            if d.is_dir() and _old(d, now, 3600):
                files.append(d)
    elif action in ('orphans', 'sources'):
        used = _used_sources(clips.values())
        for f in data.glob('*.mp4'):
            # a video imported today may still be open in the editor, so unused sources must be a day old
            if f.stem in clips or not _old(f, now, 86400 if action == 'orphans' else 3600):
                continue
            if action == 'orphans' and f.stem not in used:
                files.append(f)
            elif action == 'sources' and f.stem in used:
                files.append(f)
    elif action == 'old_clips':
        cutoff = now - max(1, int(days)) * 86400
        for clip_id in clips:
            mp4 = data / (clip_id + '.mp4')
            if mp4.exists() and mp4.stat().st_mtime < cutoff:
                files.extend(clip_files(data, clip_id))
    else:
        raise ValueError('Unknown clean-up action.')
    files = [f for f in files if _inside(data, f)]
    return {'files': files, 'bytes': sum(_size(f) for f in files)}


def _dedupe(files):
    dirs = [f for f in files if f.is_dir()]
    return [f for f in files if f.is_dir() or not any(d in f.parents for d in dirs)]


def apply(data, action, days=30):
    """Delete what plan() lists. Returns {'freed': bytes, 'deleted': n, 'failed': n}."""
    result = plan(data, action, days)
    freed = deleted = failed = 0
    for f in result['files']:
        size = _size(f)
        try:
            shutil.rmtree(f) if f.is_dir() else f.unlink()
            freed += size
            deleted += 1
        except OSError:
            failed += 1
    return {'freed': freed, 'deleted': deleted, 'failed': failed}


def delete_clips(data, ids, with_sources=False):
    """Permanently delete finished clips (video, captions, cover, record) and the older versions they replaced.
    With with_sources, also the source video of those clips when no remaining clip uses it. Unknown ids are ignored."""
    data = Path(data)
    clips = clip_records(data)
    chosen = [i for i in dict.fromkeys(ids or []) if isinstance(i, str) and HEX.match(i) and i in clips]
    victims = set(chosen)
    try:
        from reedit import ancestors
        for i in chosen:
            victims.update(a for a in ancestors(data, i) if HEX.match(a))
    except Exception:       # noqa: BLE001 - older versions are a bonus, never a reason to fail
        pass
    freed = removed = 0
    sources = set()
    for v in victims:
        record = clips.get(v) or {}
        if record.get('source'):
            sources.add(str(record['source']))
        if (record.get('settings') or {}).get('origin_id'):
            sources.add(str(record['settings']['origin_id']))
        for f in clip_files(data, v):
            size = _size(f)
            try:
                f.unlink()
                freed += size
            except OSError:
                pass
        removed += 1
    source_count = 0
    if with_sources:
        used = _used_sources(clip_records(data).values())
        for s in sources:
            p = data / (s + '.mp4')
            if HEX.match(s) and s not in used and p.exists():
                size = _size(p)
                try:
                    p.unlink()
                    freed += size
                    source_count += 1
                except OSError:
                    pass
    return {'deleted': len(chosen), 'removed_files_for': removed, 'sources': source_count, 'freed': freed}


def summary(data):
    data = Path(data)
    total = _size(data)
    clips = clip_records(data)
    clip_bytes = sum(_size(f) for c in clips for f in clip_files(data, c))
    models = _size(data / 'models')
    usage = shutil.disk_usage(data)
    plans = {a: plan(data, a) for a in ACTIONS if a != 'old_clips'}
    return {
        'folder': str(data.resolve()), 'total': total, 'free': usage.free, 'disk_total': usage.total,
        'clips': {'count': len(clips), 'bytes': clip_bytes},
        'models': models,
        'actions': {a: {'count': len(p['files']), 'bytes': p['bytes']} for a, p in plans.items()},
    }


# ---- choosing another data folder (read by compat.py at start-up, before anything uses the data folder)
def settings_path(root):
    return Path(root) / 'neon_paths.json'


def configured_folder(root):
    try:
        value = json.loads(settings_path(root).read_text(encoding='utf-8')).get('data_dir')
        return str(value) if value else ''
    except (OSError, ValueError, AttributeError):
        return ''


def validate_folder(value):
    """Absolute path to an existing or creatable, writable folder, or ValueError."""
    text = str(value or '').strip().strip('"')
    if not text or len(text) > 400:
        raise ValueError('Enter the full path of a folder, for example D:\\BloomClippingData')
    path = Path(text)
    if not path.is_absolute():
        raise ValueError('Use a full path that starts with a drive letter (C:\\...) or a slash.')
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / '.neon_write_test'
        probe.write_text('ok', encoding='utf-8')
        probe.unlink()
    except OSError:
        raise ValueError('That folder cannot be created or written to. Choose another one.') from None
    return path.resolve()


def save_folder(root, value):
    if str(value or '').strip() == '':
        try:
            settings_path(root).unlink()
        except OSError:
            pass
        return ''
    path = validate_folder(value)
    settings_path(root).write_text(json.dumps({'data_dir': str(path)}), encoding='utf-8')
    return str(path)


def attach(app, data, root, busy_fn, restart_fn):
    from fastapi import HTTPException
    from fastapi.responses import JSONResponse

    @app.get('/storage')
    def storage_summary():
        out = summary(data)
        out['configured'] = configured_folder(root)
        out['busy'] = bool(busy_fn())
        return out

    @app.get('/storage/plan')
    def storage_plan(action: str, days: int = 30):
        try:
            p = plan(data, action, days)
        except ValueError as e:
            raise HTTPException(400, str(e))
        return {'count': len(p['files']), 'bytes': p['bytes'], 'examples': [f.name for f in p['files'][:5]]}

    @app.post('/library/delete')
    def library_delete(body: dict):
        if body.get('confirm') is not True:
            raise HTTPException(400, 'Confirm the delete first.')
        ids = body.get('ids')
        if not isinstance(ids, list) or not 1 <= len(ids) <= 500:
            raise HTTPException(400, 'Choose between 1 and 500 clips.')
        return delete_clips(data, ids, bool(body.get('with_sources')))

    @app.post('/storage/open')
    def storage_open():
        import subprocess, sys
        try:
            if sys.platform == 'win32':
                os.startfile(str(Path(data).resolve()))      # noqa: S606 - opens the user's own data folder
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', str(Path(data).resolve())])
            else:
                subprocess.Popen(['xdg-open', str(Path(data).resolve())])
        except OSError:
            raise HTTPException(500, 'The folder could not be opened.')
        return {'ok': True}

    @app.post('/storage/clean')
    def storage_clean(body: dict):
        action = str(body.get('action') or '')
        if action not in ACTIONS:
            raise HTTPException(400, 'Unknown clean-up action.')
        if body.get('confirm') is not True:
            raise HTTPException(400, 'Confirm the clean-up first.')
        if busy_fn():
            raise HTTPException(409, 'A job is running. Wait until it finishes, then clean up.')
        try:
            return apply(data, action, int(body.get('days') or 30))
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.post('/storage/folder')
    def storage_folder(body: dict):
        if busy_fn():
            raise HTTPException(409, 'A job is running. Wait until it finishes, then change the folder.')
        try:
            chosen = save_folder(root, body.get('path'))
        except ValueError as e:
            raise HTTPException(400, str(e))
        if body.get('restart', True):
            restart_fn()
        return JSONResponse({'ok': True, 'folder': chosen or 'default', 'restarting': bool(body.get('restart', True))})
