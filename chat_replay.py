"""Chat replay of a finished stream (3C): where chat exploded, how many different people, and what kind of moment it was.

Live clipping already reads chat while a stream runs. For a finished stream the chat is still there:
  - YouTube: the "live_chat" replay yt-dlp offers for past live streams (text only, downloaded once and cached).
  - Twitch VOD: the public web comments endpoint every chat-replay tool uses (best effort; if Twitch refuses, nothing changes).
Signals per second, judged against this stream's own chat (a small channel's burst of 12 counts like a big one's 300):
  people  - different chatters (one spammer cannot fake a spike; PeakCut counts people the same way)
  kind    - KEKW/LUL/haha/😂 = funny, POG/W/🔥/insane = hype, monkaS/😱 = scare, F/L/💀 = fail, "clip it" = viewers asking
Chat reacts after the moment (stream delay + typing), so the curve is moved LAG seconds earlier.
Ideas from Clips Kitty's chat_moments.py and hype.py (AGPL, idea only; code written here). Light: text only, no model.
"""
import json
import re
import urllib.request
from pathlib import Path

import numpy as np

LAG = 6
KINDS = {
    'funny': re.compile(r'\b(kekw|lul|lmao+|lol+|omegalul|haha+|hahaha|xd|icant|😂|🤣)|😂|🤣', re.I),
    'hype': re.compile(r'\b(pog+|pogchamp|poggers|w+|insane|lets+ go+|sheesh|goat|clutch|holy)\b|🔥|🐐', re.I),
    'scare': re.compile(r'\b(monkas|scary|jumpscare|ahh+)\b|😱|😨', re.I),
    'fail': re.compile(r'^(f|l|rip)$|\b(rip|throw|throwing|bruh)\b|💀', re.I),     # not 'ff': in India that is Free Fire
    'clip': re.compile(r'\bclip (it|that|this)\b|\bclipped\b', re.I),
}
MAX_MESSAGES = 400_000
# YouTube writes emoji as names (:face_with_tears_of_joy:)
KINDS['funny'] = re.compile(KINDS['funny'].pattern + r'|tears_of_joy|tears-of-joy|rolling_on_the_floor|rofl', re.I)
KINDS['hype'] = re.compile(KINDS['hype'].pattern + r'|:fire:|:goat:|:exploding_head:', re.I)
KINDS['fail'] = re.compile(KINDS['fail'].pattern + r'|:skull:', re.I)
KINDS['scare'] = re.compile(KINDS['scare'].pattern + r'|:face_screaming|:fearful', re.I)
# greetings and requests are not a reaction to the moment
NOISE = re.compile(r'^\W*(hi+|hii+|hello|hey|helo|namaste|big fan|shout ?out.*|op|nice|bhai|ajju bhai.*|love you.*|reply.*|pin.*|[:\w-]*waving[:\w-]*|\W*)\W*$', re.I)


def _youtube(info, url, cache):
    subs = (info or {}).get('subtitles') or {}
    if 'live_chat' not in subs:
        return None
    target = cache / f"chat-{re.sub(r'[^A-Za-z0-9_-]', '', str(info.get('id') or 'yt'))}.live_chat.json"
    if not target.exists():
        import ytdl
        opts = {'skip_download': True, 'writesubtitles': True, 'subtitleslangs': ['live_chat'], 'quiet': True, 'no_warnings': True, 'noprogress': True,
                'outtmpl': str(target.with_suffix('').with_suffix(''))}
        with ytdl.YDL(opts) as y:
            y.download([url])
    if not target.exists():
        return None
    out = []
    with open(target, encoding='utf-8', errors='replace') as f:
        for line in f:
            try:
                row = json.loads(line)
                act = row.get('replayChatItemAction') or {}
                t = float(act.get('videoOffsetTimeMsec', 0)) / 1000
                for a in act.get('actions') or []:
                    item = ((a.get('addChatItemAction') or {}).get('item') or {}).get('liveChatTextMessageRenderer')
                    if not item:
                        continue
                    text = ''.join(r.get('text') or ((r.get('emoji') or {}).get('shortcuts') or [''])[0] for r in (item.get('message') or {}).get('runs') or [])
                    out.append((t, str(item.get('authorExternalChannelId') or ''), text))
            except (ValueError, TypeError, AttributeError):
                continue
            if len(out) >= MAX_MESSAGES:
                break
    return out


def _twitch(info):
    vid = re.sub(r'\D', '', str((info or {}).get('id') or ''))
    if not vid or 'twitch' not in str((info or {}).get('extractor') or '').lower():
        return None
    out, cursor = [], None
    for _ in range(3000):
        variables = {'videoID': vid, **({'cursor': cursor} if cursor else {'contentOffsetSeconds': 0})}
        body = json.dumps([{'operationName': 'VideoCommentsByOffsetOrCursor', 'variables': variables,
                            'extensions': {'persistedQuery': {'version': 1, 'sha256Hash': 'b70a3591ff0f4e0313d126c6a1502d79a1c02baebb288227c582044aa76adf6a'}}}]).encode()
        req = urllib.request.Request('https://gql.twitch.tv/gql', body, {'Client-ID': 'kimne78kx3ncx6brgo4mv6wki5h1ko', 'Content-Type': 'text/plain'})
        data = json.loads(urllib.request.urlopen(req, timeout=20).read())
        edges = ((((data[0].get('data') or {}).get('video') or {}).get('comments') or {}).get('edges')) or []
        if not edges:
            break
        for e in edges:
            n = e.get('node') or {}
            text = ''.join(f.get('text') or '' for f in ((n.get('message') or {}).get('fragments') or []))
            out.append((float(n.get('contentOffsetSeconds') or 0), str((n.get('commenter') or {}).get('id') or ''), text))
        cursor = edges[-1].get('cursor')
        if not cursor or len(out) >= MAX_MESSAGES:
            break
    return out or None


def load(info, url, cache):
    """[(seconds, author, text)] or None. Never raises."""
    cache = Path(cache)
    for reader in (lambda: _youtube(info, url, cache), lambda: _twitch(info)):
        try:
            rows = reader()
        except Exception:      # noqa: BLE001 - no chat replay is never a failure
            rows = None
        if rows:
            return rows
    return None


def signals(rows, duration):
    """{'heat': per-second 0..1 (unique-people burst vs this chat's own level, moved LAG s earlier), 'kinds': {kind: per-second counts}}"""
    if not rows or not duration:
        return None
    n = int(np.ceil(duration)) + 1
    people = [set() for _ in range(n)]
    kinds = {k: np.zeros(n) for k in KINDS}
    skip = 60          # messages written before the stream started all sit at 0 s, and the first minute is greetings
    for t, who, text in rows:
        s = int(t) - LAG
        if t <= skip or not 0 <= s < n or NOISE.match(text or ''):
            continue
        people[s].add(who or text[:20])
        for k, rx in KINDS.items():
            if rx.search(text or ''):
                kinds[k][s] += 1
    count = np.array([len(p) for p in people], float)
    if count.sum() < 30:
        return None
    k = np.ones(5) / 5
    smooth = np.convolve(np.pad(count, 2, mode='edge'), k, 'valid')
    base = np.convolve(np.pad(count, 60, mode='edge'), np.ones(121) / 121, 'valid') + .5     # padded: no fake burst at the edges
    burst = np.clip(smooth / base - 1, 0, None)
    burst[-30:] = 0                                    # the last half minute is goodbyes
    top = float(np.percentile(burst[burst > 0], 95)) if (burst > 0).any() else 0
    heat = np.clip(burst / top, 0, 1) if top > 0 else np.zeros(n)
    return {'heat': heat[:n - 1], 'kinds': {kk: np.convolve(v, k, 'same')[:n - 1] for kk, v in kinds.items()}}


def describe(sig, start, end):
    """(chat score 0..1, dominant kind or None) for a clip; chat may react up to 10 s after the clip ends."""
    if not sig:
        return None, None
    a, b = int(max(0, start)), int(min(len(sig['heat']), end + 10))
    if b <= a:
        return None, None
    score = float(sig['heat'][a:b].max())
    totals = {k: float(v[a:b].sum()) for k, v in sig['kinds'].items()}
    kind = max(totals, key=totals.get)
    return score, (kind if totals[kind] >= 3 else None)
