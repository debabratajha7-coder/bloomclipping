"""Speed modes: Fast, Balanced, Best. One list says which feature runs in which mode and how heavy it is.

Creator's rule (24 Nov): most people use Fast, so everything light runs in Fast; medium-load features join in Balanced; the heaviest
only in Best. Any single feature can still be switched on or off by hand in any mode ("What runs" tiles), so a weak PC can stay
fast and a strong PC can add one heavy thing without going to Best.
"""
MODES = ('fast', 'balanced', 'deep')
LABELS = {'fast': 'Fast', 'balanced': 'Balanced', 'deep': 'Best'}

# key, name, one plain line, load (light / medium / heavy), modes it is on in by default
CATALOG = [
    ('hinglish', 'Hinglish captions', 'Hindi written in English letters, chat style (ja raha hoon).', 'light', MODES),
    ('your_words', 'Your words', 'Names and words you fixed once are spelled right every time.', 'light', MODES),
    ('full_thought', 'Clean endings', 'Clips end where the sentence ends, never on "aur" or "matlab".', 'light', MODES),
    ('game_aware', 'Game aware', 'Knows GTA 6, BGMI, Free Fire...: better hooks and the game hashtags.', 'light', MODES),
    ('post_text', 'Post text', 'Punch words lit up in captions, hashtags and a one-line description.', 'light', MODES),
    ('most_replayed', 'Most replayed', 'Uses YouTube\'s "most replayed" hills on popular videos.', 'light', MODES),
    ('game_sounds', 'Game sounds', 'Gunfire, explosions and crashes count, even if the streamer is quiet.', 'light', MODES),
    ('chat_replay', 'Chat replay', 'Reads a finished stream\'s chat: where it exploded and why (funny, hype, fail).', 'light', MODES),
    ('skip_frozen', 'Skip frozen screens', 'No clips from ads, "be right back" or loading screens.', 'light', MODES),
    ('rerank', 'Compare the best', 'The AI compares the best moments side by side before choosing.', 'light', MODES),
    ('caption_fix', 'AI spelling fix', 'The AI fixes numbers, names and spellings in captions, word by word.', 'medium', ('balanced', 'deep')),
    ('whole_pass', 'AI reads everything', 'The AI reads the whole talk, so quiet funny lines are not missed.', 'medium', ('balanced', 'deep')),
    ('fair_order', 'Fair comparing', 'The comparison is done twice in opposite order, so no clip loses for being last.', 'heavy', ('deep',)),
    ('facecam_check', 'Verify facecam', 'Checks a single facecam crop with a local Gemma vision model, when installed.', 'medium', ()),
    ('face_reaction', 'Facecam reactions', 'Optional Best-mode cue from a visible laugh or surprise in one frame.', 'heavy', ()),
    ('deep_scan', 'Full video scan', 'Downloads the whole video and scans every frame for movement (slow, most thorough).', 'heavy', ('deep',)),
]
KEYS = [row[0] for row in CATALOG]


def resolve(mode, overrides=None):
    """{feature: bool} for a request. Unknown keys and non-bool values in `overrides` are ignored."""
    mode = mode if mode in MODES else 'fast'
    flags = {key: mode in modes for key, _n, _l, _w, modes in CATALOG}
    for key, value in (overrides or {}).items() if isinstance(overrides, dict) else ():
        if key in flags and isinstance(value, bool):
            flags[key] = value
    return flags


def catalog():
    return {'modes': [{'key': m, 'label': LABELS[m]} for m in MODES],
            'features': [{'key': k, 'name': n, 'line': l, 'load': w, 'modes': list(ms)} for k, n, l, w, ms in CATALOG]}


def attach(app):
    @app.get('/modes')
    def list_modes():
        return catalog()
