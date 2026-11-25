"""Your words list: fix a word once and every future caption, hook and title spells it right.

YouTube captions and the speech model hear the same names and English words wrong again and again (एंडी -> "endi" for Andy,
"pulis" for police, "vice siti" for Vice City). Each entry maps what was written to what it should be. Matching is whole-word and
ignores case and the small Devanagari spelling differences (nukta, chandrabindu), so one entry covers the usual variants.
An entry may also replace two or three words in a row ("vice siti" -> "Vice City"). Word timings never move.

Stored in data/preferences/glossary.json, on this computer only.
"""
import json
import re
import threading

from loanwords import _norm

MAX_ENTRIES = 500
_LOCK = threading.Lock()
_PATH = None
_CACHE = {'mtime': None, 'entries': []}
_EDGE = re.compile(r'^((?:[^\wऀ-ॿ]|[।॥])*)(.*?)((?:[^\wऀ-ॿ]|[।॥])*)$', re.S)   # ।॥ count as punctuation


def _key(text):
    return ' '.join(_norm(str(text)).casefold().split())


def _clean(value, name):
    value = ' '.join(str(value or '').split())
    if not 1 <= len(value) <= 60:
        raise ValueError(f'{name}: use 1-60 characters.')
    if len(value.split()) > 3:
        raise ValueError(f'{name}: at most 3 words.')
    return value


def setup(data):
    global _PATH
    _PATH = data / 'preferences' / 'glossary.json'


def entries():
    """[{'from': ..., 'to': ...}], newest first. Cached until the file changes."""
    if _PATH is None or not _PATH.exists():
        return []
    mtime = _PATH.stat().st_mtime
    if _CACHE['mtime'] != mtime:
        try:
            rows = json.loads(_PATH.read_text(encoding='utf-8'))
            _CACHE['entries'] = [r for r in rows if isinstance(r, dict) and r.get('from') and r.get('to')]
        except (OSError, ValueError):
            _CACHE['entries'] = []
        _CACHE['mtime'] = mtime
    return list(_CACHE['entries'])


def _save(rows):
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = _PATH.with_suffix('.tmp')
    temp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(_PATH)
    _CACHE['entries'], _CACHE['mtime'] = list(rows), _PATH.stat().st_mtime    # two saves in the same clock tick must not read stale rows


def add(wrong, right):
    wrong, right = _clean(wrong, 'Written as'), _clean(right, 'Should be')
    if _key(wrong) == _key(right) and wrong == right:
        raise ValueError('Both sides are the same.')
    with _LOCK:
        rows = [r for r in entries() if _key(r['from']) != _key(wrong)]
        if len(rows) >= MAX_ENTRIES:
            raise ValueError(f'At most {MAX_ENTRIES} words. Remove one first.')
        rows.insert(0, {'from': wrong, 'to': right})
        _save(rows)
    return rows


def remove(wrong):
    with _LOCK:
        rows = [r for r in entries() if _key(r['from']) != _key(wrong)]
        _save(rows)
    return rows


def _table(rows):
    table = {}
    for r in rows:
        table.setdefault(len(r['from'].split()), {})[_key(r['from'])] = r['to']
    return table


def fix_text(text, rows=None):
    """A hook or title with every listed word replaced."""
    rows = entries() if rows is None else rows
    if not rows or not text:
        return text
    words = [{'text': t, 'start': 0, 'end': 0} for t in str(text).split()]
    return ' '.join(w['text'] for w in fix_words(words, rows))


def fix_words(words, rows=None):
    """Caption words with listed words replaced. A phrase entry keeps the first word's start and the last word's end."""
    rows = entries() if rows is None else rows
    if not rows or not words:
        return words
    table = _table(rows)
    lengths = sorted(table, reverse=True)
    out, i = [], 0
    while i < len(words):
        for n in lengths:
            if i + n > len(words):
                continue
            parts = [_EDGE.match(str(w.get('text', ''))).groups() for w in words[i:i + n]]
            core = ' '.join(p[1] for p in parts)
            hit = table[n].get(_key(core))
            if hit is not None:
                lead, tail = parts[0][0], parts[-1][2]
                out.append(dict(words[i], text=lead + hit + tail, end=words[i + n - 1].get('end', words[i].get('end'))))
                i += n
                break
        else:
            out.append(words[i])
            i += 1
    return out


def attach(app, data):
    from fastapi import HTTPException
    setup(data)

    @app.get('/glossary')
    def list_words():
        return {'words': entries(), 'max': MAX_ENTRIES}

    @app.post('/glossary')
    def add_word(body: dict):
        try:
            return {'words': add(body.get('from'), body.get('to'))}
        except (ValueError, TypeError) as error:
            raise HTTPException(400, str(error))

    @app.post('/glossary/remove')
    def remove_word(body: dict):
        return {'words': remove(str(body.get('from', '')))}
