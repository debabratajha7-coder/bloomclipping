import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import friendly


class Friendly(unittest.TestCase):
    def plain(self, text):
        return friendly.explain(text)[0]

    def test_common_failures_become_plain_sentences(self):
        cases = {
            'ERROR: [youtube] abc: Private video. Sign in if you\'ve been granted access': 'private',
            'ERROR: [youtube] abc: Video unavailable': 'not available',
            "OSError: [Errno 28] No space left on device": 'disk is full',
            'urllib.error.URLError: <urlopen error [Errno 11001] getaddrinfo failed>': 'No internet',
            "ERROR: Unsupported URL: https://example.com/page": 'not a video',
            "FileNotFoundError: [WinError 2] The system cannot find the file specified: 'ffmpeg' not found": 'FFmpeg',
            'ERROR: [youtube] abc: Sign in to confirm your age. This video may be inappropriate for some users.': 'age-restricted',
            'ERROR: This video is not available in your country': 'blocked in your country',
        }
        for raw, key in cases.items():
            self.assertIn(key.lower(), self.plain(raw).lower(), raw)
            self.assertIn('\n', self.plain(raw))                    # English line + Hinglish line

    def test_original_text_kept_for_reports(self):
        plain, original = friendly.explain('ERROR: Private video')
        self.assertEqual(original, 'ERROR: Private video'); self.assertNotEqual(plain, original)

    def test_unknown_and_already_plain_pass_through(self):
        self.assertEqual(friendly.explain('Something odd happened')[0], 'Something odd happened')
        guide = 'YouTube blocked this download (its bot check). Fix: ...'
        self.assertEqual(friendly.explain(guide)[0], guide)


if __name__ == '__main__':
    unittest.main()
