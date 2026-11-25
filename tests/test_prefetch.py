import sys, time, unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import prefetch


class FakeYDL:
    calls = 0
    def __init__(self, opts): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def extract_info(self, url, download=False):
        FakeYDL.calls += 1; time.sleep(.2); return {'id': 'x', 'duration': 600}


class Prefetch(unittest.TestCase):
    def test_fetched_once_and_reused(self):
        prefetch._cache.clear(); FakeYDL.calls = 0
        with mock.patch('captions_yt.from_info', return_value=[{'start': 0, 'end': 1, 'text': 'hi'}]):
            prefetch.start('https://youtu.be/abc', FakeYDL); prefetch.start('https://youtu.be/abc', FakeYDL)
            info, words = prefetch.get('https://youtu.be/abc', wait=5)
        self.assertEqual(info['id'], 'x'); self.assertEqual(words[0]['text'], 'hi'); self.assertEqual(FakeYDL.calls, 1)

    def test_unknown_url(self):
        self.assertEqual(prefetch.get('https://youtu.be/none', wait=0), (None, None))


if __name__ == '__main__':
    unittest.main()
