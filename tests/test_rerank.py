import json, sys, unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import smart


def clips():
    return [{'rank': .70, 'transcript': 'boring filler words here today'}, {'rank': .69, 'transcript': 'the shark saw us and we ran'},
            {'rank': .68, 'transcript': 'police chase ends in a huge crash'}, {'rank': .30, 'transcript': 'short'}]


class Rerank(unittest.TestCase):
    def test_best_compared_moves_up(self):
        cs = clips()
        with mock.patch('llm.complete', return_value=json.dumps({'order': [3, 2, 1]})):
            self.assertTrue(smart.rerank(cs, 'x', 2))
        best = max(cs, key=lambda c: c['rank'])
        self.assertIn('crash', best['transcript'])
        self.assertEqual(cs[3]['rank'], .30)                 # too short to compare: untouched

    def test_reverse_sample_cancels_last_place_bias(self):
        cs = clips(); answers = iter([json.dumps({'order': [1, 2, 3]}), json.dumps({'order': [3, 2, 1]})])
        with mock.patch('llm.complete', side_effect=lambda *a: next(answers)):
            smart.rerank(cs, 'x', 2, samples=2)
        self.assertEqual(cs[0]['head_to_head'], cs[2]['head_to_head'])

    def test_bad_answer_keeps_ranks_with_unlisted_at_end(self):
        cs = clips()
        with mock.patch('llm.complete', return_value=json.dumps({'order': ['x', 9, 2]})):
            smart.rerank(cs, 'x', 2)
        self.assertEqual(cs[1]['head_to_head'], 1.0)

    def test_no_model(self):
        self.assertFalse(smart.rerank(clips(), None, 2))


if __name__ == '__main__':
    unittest.main()
