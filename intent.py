"""Clip direction (3E): plain words in the focus box become times and styles.

"funny moments first, more from around 1:35:00, the police chase near the end" ->
  spans:  [(5640, 5760), (last 15% of the video)]   time ranges read by this code, never by the AI
  styles: {'humour'}                                  kinds of moment to prefer
Like Clips Kitty's intent.py (idea only, code written here) it only ADDS: clips inside an asked span or of an asked style get points
and extra candidates are looked at inside the spans; nothing is filtered out, so a wrong guess never loses clips.
Hinglish works too: "1:35 ke paas", "end mein", "shuru mein", "hasi wale".

EXACT TIMES (24 Nov): when the text is only a time ("1:35:00", "1:35:00 to 1:36:00", "5700s", "1h35m", "minute 95") the user wants
that clip, not a hint. explicit() turns it into exact moments: a range is cut as written; a single time starts there and runs the
usual clip length. Any other words (a topic, a style) keep the hint behaviour above.
"""
import re

_UNITS = r'(?:hours?|hrs?|h|ghante?|ghanta|minutes?|mins?|minat|m|seconds?|secs?|s)'
_COMBO = r'\d+(?:\.\d+)?\s*' + _UNITS + r'(?![a-z])(?:\s*(?:and\s+)?\d+(?:\.\d+)?\s*' + _UNITS + r'(?![a-z])){0,2}'
_T = r'(\d{1,2}:\d{2}(?::\d{2})?(?!\d)|' + _COMBO + r')'
_RANGE = re.compile(_T + r'\s*(?:-|–|—|to|se|till|tak|until)\s*' + _T, re.I)
_ONE = re.compile(_T, re.I)
_MINUTE_WORD = re.compile(r'\b(?:minute|min|minat)\s+(\d{1,3})\b(?!\s*:)', re.I)
_COUNT = re.compile(r'\b(\d{1,2})\s*(?:clips?|moments?|shorts?)\b(?!\s+(?:in|at|per)\b)', re.I)
STYLE_WORDS = {
    'humour': ('funny', 'comedy', 'joke', 'laugh', 'hasi', 'hansi', 'mazak', 'mazaak', 'meme', 'lol'),
    'action': ('hype', 'action', 'fight', 'chase', 'kill', 'clutch', 'crash', 'police', 'shootout', 'ladai', 'maar'),
    'reaction': ('reaction', 'react', 'shock', 'scream', 'rage', 'gussa', 'chilla'),
    'story': ('story', 'kahani', 'emotional', 'sad', 'storytime'),
    'opinion': ('opinion', 'hot take', 'rant', 'take'),
    'insight': ('tip', 'tips', 'tutorial', 'how to', 'trick', 'sikh'),
}
# words that may sit around a time without turning it into a topic ("clip at 1:35:00", "1:35:00 se 1:36:00 tak")
FILLER = {'clip', 'clips', 'at', 'from', 'to', 'till', 'until', 'se', 'tak', 'around', 'near', 'ke', 'paas', 'pe', 'par', 'mein', 'me', 'timestamp',
          'time', 'make', 'a', 'the', 'one', 'banao', 'bana', 'do', 'de', 'kar', 'karo', 'please', 'this', 'that', 'wala', 'wali', 'moment',
          'minute', 'minutes', 'min', 'sec', 'seconds', 'hour', 'hours', 'of', 'video', 'cut', 'kato', 'kaato', 'is', 'ka', 'ki', 'ko', 'and', 'aur',
          'hindi', 'english', 'start', 'end', 'between', 'ye', 'yeh', 'wo', 'woh', 'iska', 'isko', 'chahiye', 'chahie', 'only', 'sirf'}


def seconds(token):
    token = token.strip().lower()
    if ':' in token:
        parts = [float(p) for p in token.split(':')]
        return parts[0] * 3600 + parts[1] * 60 + parts[2] if len(parts) == 3 else parts[0] * 60 + parts[1]
    total, found = 0.0, False
    for value, unit in re.findall(r'(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|ghante?|ghanta|minutes?|mins?|minat|m|seconds?|secs?|s)(?![a-z])', token):
        found = True
        total += float(value) * (3600 if unit[0] == 'h' or unit.startswith('ghant') else 60 if unit[0] == 'm' else 1)
    return total if found else None


def requested_count(text, default):
    match = _COUNT.search(text or '')
    return max(1, min(12, int(match.group(1)))) if match else default


def _times(text):
    """([(start, end)] for 'A to B', [t] for single times) found in the text, in order of appearance."""
    ranges, singles, taken = [], [], []
    for m in _RANGE.finditer(text):
        a, b = seconds(m.group(1)), seconds(m.group(2))
        if a is not None and b is not None and b > a:
            ranges.append((m.start(), a, b)); taken.append(m.span())
    for m in _ONE.finditer(text):
        if any(s <= m.start() < e for s, e in taken):
            continue
        t = seconds(m.group(1))
        if t is not None:
            singles.append((m.start(), t)); taken.append(m.span())
    for m in _MINUTE_WORD.finditer(text):
        if any(s <= m.start() < e for s, e in taken):
            continue
        singles.append((m.start(), int(m.group(1)) * 60.0)); taken.append(m.span())
    return [(a, b) for _p, a, b in sorted(ranges)], [t for _p, t in sorted(singles)], taken


def explicit(text, min_len=30, max_len=60, limit=12):
    """Exact moments [{'start','end','snap'}] when the text is only times; [] when it also has other words (a topic or style)."""
    text = str(text or '')
    ranges, singles, taken = _times(text)
    if not ranges and not singles:
        return []
    rest = text
    for s, e in sorted(taken, reverse=True):
        rest = rest[:s] + ' ' + rest[e:]
    words = [w for w in re.findall(r"[A-Za-zऀ-ॿ']+", rest.lower()) if w not in FILLER]
    low = text.lower()
    if len(words) >= 2 or any(re.search(r'\b' + re.escape(w) + r'\b', low) for ws in STYLE_WORDS.values() for w in ws):
        return []      # a topic or a style was asked too: keep the hint behaviour
    length = max(10.0, min(180.0, (float(min_len) + float(max_len)) / 2))
    out = [{'start': round(a, 2), 'end': round(min(b, a + 180), 2), 'snap': False} for a, b in ranges]
    out += [{'start': round(max(0.0, t - .3), 2), 'end': round(max(0.0, t - .3) + length, 2), 'snap': True} for t in singles]
    return out[:limit]


def parse(text, duration):
    text = str(text or '')
    low = text.lower()
    ranges, singles, _taken = _times(text)
    spans = [(a, b) for a, b in ranges] + [(t - 60, t + 60) for t in singles]
    if duration:
        if re.search(r'\b(near the end|at the end|end mein|end me|last part|aakhir|akhir|ending)\b', low):
            spans.append((duration * .85, duration))
        if re.search(r'\b(at the start|beginning|shuru|starting|opening part)\b', low):
            spans.append((0, duration * .15))
        if re.search(r'\b(middle|beech|bich)\b', low):
            spans.append((duration * .4, duration * .6))
    clean = []
    for a, b in spans:
        a, b = max(0.0, a), min(float(duration or b), b)
        if b - a >= 5:
            clean.append((round(a, 1), round(b, 1)))
    styles = {kind for kind, words in STYLE_WORDS.items() if any(re.search(r'\b' + re.escape(w) + r'\b', low) for w in words)}
    return {'spans': clean[:8], 'styles': styles}


def inside(clip, spans):
    """Share of the clip that falls in any asked span (0..1)."""
    if not spans:
        return 0.0
    length = max(0.1, clip['end'] - clip['start'])
    return max(max(0.0, min(clip['end'], b) - max(clip['start'], a)) / length for a, b in spans)


def boost(clip, direction):
    """Rank bonus for a clip that matches the direction: up to +0.25 for an asked span, +0.08 for an asked style."""
    bonus = .25 * inside(clip, direction.get('spans') or [])
    if clip.get('kind') in (direction.get('styles') or ()):
        bonus += .08
    return bonus
