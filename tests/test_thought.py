import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import thought, smart


def timed(spec):
    """'word@start-end ...'"""
    out = []
    for tok in spec.split():
        w, t = tok.rsplit('@', 1); a, b = t.split('-')
        out.append({'text': w, 'start': float(a), 'end': float(b)})
    return out


class SentenceEnds(unittest.TestCase):
    def test_punctuation(self):
        ws = timed('He@0-.3 ran.@.4-.8 Then@.9-1.2 stopped.@1.3-1.6 ok.@1.7-2')
        self.assertEqual(thought.sentence_ends(ws), [.8, 1.6, 2.0])

    def test_pause_without_punctuation_but_not_on_connector(self):
        ws = timed('bhai@0-.3 chalo@.4-.7 aur@.8-1 phir@2-2.3 dekho@2.4-2.7')
        self.assertEqual(thought.sentence_ends(ws), [2.7])        # 'aur' before a 1 s pause is not an end

    def test_capital_after_gap(self):
        ws = timed('we@0-.2 won@.3-.5 Next@.6-.8 game@.9-1.1')
        self.assertIn(.5, thought.sentence_ends(ws))


class SnapEnd(unittest.TestCase):
    def test_extends_to_finish_sentence(self):
        ws = timed('this@0-.5 is@9-9.5 the@10-10.3 best@10.4-10.8 car.@10.9-11.3 Next@12-12.4')
        self.assertAlmostEqual(thought.snap_end(ws, 0, 10.5, 5, 30), 11.6, places=2)

    def test_pulls_back_when_end_too_far(self):
        ws = timed('one.@0-9 two@9.1-9.5 ' + ' '.join(f'w{i}@{10+i}-{10.5+i}' for i in range(15)))
        self.assertAlmostEqual(thought.snap_end(ws, 0, 10, 5, 30), 9.05, places=2)

    def test_tail_stops_before_next_word(self):
        ws = timed('done.@0-4 Next@4.1-4.5')
        self.assertAlmostEqual(thought.snap_end(ws, 0, 4, 2, 30), 4.05, places=2)


class SmartSnap(unittest.TestCase):
    def test_finishes_sentence_with_extra_words(self):
        clip = {'start': 100.0, 'end': 110.0}
        words = timed('so@0-1 the@1.1-2 thing@5-6 is@8-9')
        ext = words + timed('awesome.@10.2-10.8 Next@11.5-12')
        smart.snap(clip, words, 5, 30, ext, 200)
        self.assertAlmostEqual(clip['end'], 111.1, places=1)
        self.assertEqual(words[-1]['text'], 'awesome.')


if __name__ == '__main__':
    unittest.main()
