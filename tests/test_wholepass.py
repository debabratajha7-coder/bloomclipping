import json, sys, unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wholepass


def words(n=200):
    return [{'start': i * 1.5, 'end': i * 1.5 + 1, 'text': ('baat' if i % 9 else 'hua.')} for i in range(n)]


class WholePass(unittest.TestCase):
    def test_marks_and_proposals(self):
        loud = [0.0] * 400; loud[30:33] = [1, 1, 1]
        lines = wholepass.make_lines(words(), lambda s, e: (max(loud[int(s):int(e) + 1] or [0]) > .6, False))
        self.assertTrue(any(l['loud'] for l in lines))
        answer = json.dumps({'clips': [{'start': 30, 'end': 30, 'why': 'big reaction'}, {'start': 9999, 'end': 10010}, {'start': 31, 'end': 60}]})
        with mock.patch('llm.complete', return_value=answer):
            got = wholepass.proposals('m', words(), 300, 20, 45, 3, loud=loud)
        self.assertEqual(len(got), 1)                         # out-of-window and overlapping answers dropped
        self.assertEqual((got[0]['start'], got[0]['end']), (29.8, 50.0))    # zero-length answer grown to the minimum
        self.assertIn('big reaction', got[0]['reason'])

    def test_failure_is_quiet(self):
        with mock.patch('llm.complete', side_effect=RuntimeError('HTTP 500')):
            self.assertEqual(wholepass.proposals('m', words(), 300, 20, 45, 3), [])


if __name__ == '__main__':
    unittest.main()
