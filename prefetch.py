"""Get ready while the user is still choosing settings (creator, 24 Nov).

Pasting a link (Get preview) must NOT start making clips: the clips use the caption style, layout and mode chosen afterwards and
are made only when Make clips is pressed. What can safely start early is the slow fetching that does not depend on any setting:
the video info (yt-dlp) and YouTube's own word-timed captions. They are kept in memory for 30 minutes and Make clips reuses them,
so it starts working straight away.
"""
import threading
import time

TTL = 30 * 60
_cache = {}
_lock = threading.Lock()


def _key(url):
    return str(url or '').strip()


def start(url, ydl_factory):
    """Fetch info + captions in the background (no-op if already fresh or running)."""
    key = _key(url)
    if not key:
        return
    with _lock:
        row = _cache.get(key)
        if row and (row.get('busy') or time.time() - row['at'] < TTL):
            return
        _cache[key] = {'at': time.time(), 'busy': True, 'info': None, 'words': None}

    def work():
        info = words = None
        try:
            with ydl_factory({'skip_download': True}) as y:
                info = y.extract_info(key, download=False)
            if info and not info.get('is_live'):
                from captions_yt import from_info
                try:
                    words = from_info(info)
                except Exception:      # noqa: BLE001 - no captions: Make clips falls back as before
                    words = None
        except Exception:      # noqa: BLE001 - Make clips fetches again itself
            info = None
        with _lock:
            _cache[key] = {'at': time.time(), 'busy': False, 'info': info, 'words': words}
    threading.Thread(target=work, daemon=True).start()


def get(url, wait=20):
    """(info, words) prepared earlier, waiting up to `wait` s for a fetch in progress; (None, None) if nothing usable."""
    key = _key(url)
    end = time.time() + wait
    while True:
        with _lock:
            row = _cache.get(key)
        if not row:
            return None, None
        if not row['busy']:
            if row['info'] and time.time() - row['at'] < TTL:
                return row['info'], row['words']
            return None, None
        if time.time() > end:
            return None, None
        time.sleep(.3)
