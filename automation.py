"""Automation (5H): a watch folder, a webhook, and words to avoid.

- Watch folder: drop a finished recording into one folder and BloomClipping makes clips from it by itself (even overnight). A file is
  taken only when its size has stopped changing, once; the copy goes into the app's data folder and joins the normal processing queue.
- Webhook: every finished clip is announced to one web address (Discord, Zapier, your own script) as small JSON: title, hook, score,
  hashtags and the local file link. Nothing but that text is sent; the video file is never uploaded.
- Words to avoid: a list you keep; any clip whose title, hook, description or captions contain one is flagged "check before posting".
Settings live in data/preferences/automation.json on this computer.
"""
import json
import os
import re
import shutil
import threading
import time
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import urlparse

EXT = ('.mp4', '.mkv', '.mov', '.webm', '.avi', '.flv', '.ts')
POLL = 15
DEFAULTS = {'watch_on': False, 'watch_folder': '', 'watch_count': 4, 'watch_mode': 'fast', 'webhook_url': '', 'banned': []}
_lock = threading.RLock()
_ctx = {'data': None, 'probe': None, 'queue': lambda: None, 'seen': {}, 'status': 'off', 'last': ''}


def _file(data):
    return Path(data) / 'preferences' / 'automation.json'


def read(data=None):
    data = data or _ctx['data']
    try:
        cfg = json.loads(_file(data).read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        cfg = {}
    return {**DEFAULTS, **(cfg if isinstance(cfg, dict) else {})}


def validate(body):
    """Cleaned settings from a request body, or ValueError with a plain sentence."""
    out = {}
    if 'watch_folder' in body:
        folder = str(body.get('watch_folder') or '').strip().strip('"')
        if folder and not Path(folder).is_dir():
            raise ValueError('That folder does not exist. Paste the full path of an existing folder.')
        out['watch_folder'] = folder
    if 'watch_on' in body:
        out['watch_on'] = bool(body.get('watch_on'))
    if 'watch_count' in body:
        out['watch_count'] = max(1, min(12, int(body.get('watch_count') or 4)))
    if 'watch_mode' in body:
        out['watch_mode'] = body.get('watch_mode') if body.get('watch_mode') in ('fast', 'balanced', 'deep') else 'fast'
    if 'webhook_url' in body:
        url = str(body.get('webhook_url') or '').strip()
        if url:
            p = urlparse(url)
            local = (p.hostname or '').lower() in ('127.0.0.1', 'localhost')
            if p.scheme not in ('https', 'http') or not p.hostname or p.username or p.password or (p.scheme == 'http' and not local) or len(url) > 400:
                raise ValueError('Use an https address (http only for this computer).')
        out['webhook_url'] = url
    if 'banned' in body:
        words = body.get('banned') or []
        if isinstance(words, str):
            words = re.split(r'[,\n]+', words)
        if not isinstance(words, list) or len(words) > 300:
            raise ValueError('Use at most 300 words.')
        out['banned'] = [w.strip()[:40] for w in map(str, words) if w.strip()][:300]
    if out.get('watch_on') and not (out.get('watch_folder') or read().get('watch_folder')):
        raise ValueError('Choose a folder to watch first.')
    return out


def save(data, body):
    with _lock:
        cfg = {**read(data), **validate(body)}
        _file(data).parent.mkdir(parents=True, exist_ok=True)
        tmp = _file(data).with_suffix('.tmp')
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(_file(data))
    return cfg


def lint(texts, banned):
    """Words from `banned` that appear (whole word, any case) in the given texts."""
    hay = ' '.join(str(t or '') for t in texts).casefold()
    return sorted({w for w in banned or [] if w.strip() and re.search(r'(?<!\w)' + re.escape(w.strip().casefold()) + r'(?!\w)', hay)})


def check_clip(clip_texts, data=None):
    return lint(clip_texts, read(data).get('banned'))


def notify(data, clip):
    """Tell the webhook about a finished clip (background thread, never raises)."""
    url = read(data).get('webhook_url')
    if not url:
        return

    def work():
        try:
            body = json.dumps({'event': 'clip_ready', 'app': 'BloomClipping', **{k: clip.get(k) for k in ('title', 'hook', 'score', 'hashtags', 'description', 'file', 'flags')}},
                              ensure_ascii=False).encode()
            req = urllib.request.Request(url, body, {'Content-Type': 'application/json', 'User-Agent': 'BloomClipping'})
            urllib.request.urlopen(req, timeout=8).read(1000)
        except Exception:      # noqa: BLE001 - a dead webhook must never break clipping
            pass
    threading.Thread(target=work, daemon=True).start()


def _import_file(path, cfg):
    data = _ctx['data']
    sid = uuid.uuid4().hex
    dest = Path(data) / (sid + '.mp4')
    try:
        os.link(path, dest)
    except OSError:
        shutil.copy2(path, dest)
    try:
        meta = _ctx['probe'](dest)
    except Exception:      # noqa: BLE001 - not a playable video
        dest.unlink(missing_ok=True)
        return None
    payload = {'id': sid, 'count': cfg['watch_count'], 'mode': cfg['watch_mode'], 'source_height': 1080, 'accurate': 'fast', 'min_len': 30, 'max_len': 60,
               'layout': 'blur', 'aspect': 'vertical', 'resolution': 1080, 'fps': 0, 'caption_style': 'karaoke', 'language': '', 'cam_auto': True,
               'watch_name': Path(path).name}
    queue = _ctx['queue']()
    if queue is None:
        return None
    queue.enqueue('make', payload, 0)
    return meta


def _scan_once():
    cfg = read()
    if not cfg['watch_on'] or not cfg['watch_folder'] or not Path(cfg['watch_folder']).is_dir():
        _ctx['status'] = 'off' if not cfg['watch_on'] else 'folder missing'
        return
    _ctx['status'] = 'watching'
    now = time.time()
    for f in sorted(Path(cfg['watch_folder']).iterdir()):
        if not f.is_file() or f.suffix.lower() not in EXT:
            continue
        try:
            st = f.stat()
        except OSError:
            continue
        key = f'{f.name}|{st.st_size}|{int(st.st_mtime)}'
        row = _ctx['seen'].get(key)
        if row == 'done' or st.st_size < 200_000:
            continue
        if row != st.st_size or now - st.st_mtime < 20:      # still being written: wait for a quiet poll
            _ctx['seen'][key] = st.st_size
            continue
        if _import_file(f, cfg) is not None:
            _ctx['seen'][key] = 'done'
            _ctx['last'] = f.name
        else:
            _ctx['seen'][key] = 'done'      # not a video, or no queue yet: do not retry every 15 s
    seen_file = Path(_ctx['data']) / 'preferences' / 'watch-seen.json'
    try:
        seen_file.write_text(json.dumps([k for k, v in _ctx['seen'].items() if v == 'done']), encoding='utf-8')
    except OSError:
        pass


def _loop():
    seen_file = Path(_ctx['data']) / 'preferences' / 'watch-seen.json'
    try:
        for k in json.loads(seen_file.read_text(encoding='utf-8')):
            _ctx['seen'][k] = 'done'
    except (OSError, ValueError):
        pass
    while True:
        try:
            _scan_once()
        except Exception:      # noqa: BLE001
            pass
        time.sleep(POLL)


def attach(app, data, probe):
    from fastapi import HTTPException
    _ctx.update(data=data, probe=probe, queue=lambda: getattr(app, 'processing_queue', None))

    @app.get('/automation')
    def get_settings():
        return {**read(data), 'status': _ctx['status'], 'last': _ctx['last']}

    @app.post('/automation')
    def set_settings(body: dict):
        try:
            return {**save(data, body), 'status': _ctx['status'], 'last': _ctx['last']}
        except (ValueError, TypeError) as error:
            raise HTTPException(400, str(error))

    threading.Thread(target=_loop, daemon=True, name='watch-folder').start()
