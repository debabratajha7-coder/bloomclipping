"""Clips end on a complete thought (1D + 4B).

A clip that stops mid-sentence feels cut off. A sentence ends after a word when, in order:
  1. the word carries . ? ! ... or the Hindi full stop;
  2. otherwise it is not a connector ("and", "so", "the", "matlab", "ki"...) and either a pause follows (0.6 s with punctuation in the
     transcript, 0.5 s without: YouTube auto-captions have none), or the next word starts with a capital letter after a small gap.
The end then moves to the sentence end at or just after the planned end (up to +8 s, within the maximum length); if that is too far,
it pulls back to the previous sentence end when that keeps at least 70% of the clip; otherwise it ends on a whole, non-connector word.
A short breath is added after the last word but it stops before the next word, so the next sentence never leaks in.

Rules from PeakCut's studio/brain.py (sentence_ends, _snap; MIT, Copyright (c) 2026 PeakCut contributors) and Reelsaw's documented
clip-boundary rules (docs/SELECTION.md; idea only, code written here).
"""
import re

CONNECTORS = {
    'and', 'so', 'but', 'or', 'the', 'a', 'an', 'to', 'of', 'for', 'with', 'in', 'on', 'at', 'is', 'are', 'was', 'were', 'that', 'this',
    'because', 'if', 'then', 'when', 'like', "you're", "i'm", 'my', 'your', 'his', 'her', 'their', 'our', 'i', 'we', 'you', 'he', 'she', 'it',
    'they', 'just', 'very', 'really', 'gonna', 'wanna', 'about', 'from', 'into', 'as', 'by',
    # Hinglish connectors: a clip never ends on these
    'aur', 'ki', 'ke', 'ka', 'ko', 'se', 'mein', 'me', 'par', 'toh', 'to', 'matlab', 'lekin', 'kyunki', 'jab', 'agar', 'phir', 'fir', 'ye', 'yeh',
    'wo', 'woh', 'jo', 'ne', 'bhi', 'na', 'ya', 'kya', 'isliye', 'warna', 'jaise', 'mera', 'meri', 'tera', 'apna', 'is', 'us',
}
END_MARKS = '.?!…।؟'
MAX_EXTEND = 8.0


def _bare(text):
    return re.sub(r'[^\wऀ-ॿ\']', '', str(text).lower())


def sentence_ends(words):
    """Times (same clock as the words) at which a sentence finishes."""
    if not words:
        return []
    punctuated = sum(1 for w in words if str(w['text']).rstrip()[-1:] in END_MARKS) >= max(2, len(words) // 80)
    out = []
    for i, w in enumerate(words):
        text = str(w['text']).rstrip()
        nxt = words[i + 1] if i + 1 < len(words) else None
        gap = (nxt['start'] - w['end']) if nxt else 9.0
        if text[-1:] in END_MARKS:
            out.append(w['end'])
            continue
        if _bare(text) in CONNECTORS:
            continue
        if gap >= (0.6 if punctuated else 0.5):
            out.append(w['end'])
        elif nxt and gap >= 0.05 and str(nxt['text'])[:1].isupper() and str(nxt['text']).strip(' "\'') not in ('I', "I'm"):
            out.append(w['end'])
    return out


def snap_end(words, start, end, min_len, max_len, limit=None):
    """New end (same clock as words) for a clip [start, end]. `limit` is the latest allowed end (source length or available words)."""
    limit = limit if limit is not None else (words[-1]['end'] + 1 if words else end)
    lo, hi = start + min_len, min(start + max_len, limit)
    stops = [x for x in sentence_ends(words) if lo <= x <= hi]
    if stops:
        after = [x for x in stops if x >= end - 1.0 and x - end <= MAX_EXTEND]
        before = [x for x in stops if x <= end and x - start >= .7 * (end - start)]
        new = after[0] if after else (before[-1] if before else min(stops, key=lambda x: abs(x - end)))
    else:
        ends = [w['end'] for w in words if lo <= w['end'] <= hi and _bare(w['text']) not in CONNECTORS]
        new = min(ends, key=lambda x: abs(x - end)) if ends else end
    new = max(min(new, hi), min(lo, hi))
    nxt = next((w['start'] for w in words if w['start'] > new - 0.01), None)
    tail = 0.3 if nxt is None else min(0.3, max(0.05, nxt - new - 0.05))
    return round(min(limit, new + tail), 2)
