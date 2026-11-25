import json, sys, unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import capfix


def words(text):
    return [{'start': i * .5, 'end': i * .5 + .4, 'text': w} for i, w in enumerate(text.split())]


def answer(lst):
    return mock.patch('llm.complete', return_value=json.dumps({'words': lst}))


class CapFix(unittest.TestCase):
    def test_spelling_numbers_and_merge_keep_timing(self):
        with answer(['He', 'bought', 'a', 'Lamborghini', 'for', '25', '', 'lakh.']):
            out, n = capfix.fix(words('he bought a lamborgini for twenty five lakh'), model='x')
        self.assertEqual([w['text'] for w in out], ['He', 'bought', 'a', 'Lamborghini', 'for', '25', 'lakh.'])
        self.assertEqual(out[3]['start'], 1.5)
        self.assertEqual(n, 5)

    def test_rewrite_and_devanagari_rejected(self):
        with answer(['vehicle', 'जा', 'raha']):
            out, _ = capfix.fix(words('gaadi ja raha'), model='x')
        self.assertEqual([w['text'] for w in out], ['gaadi', 'ja', 'raha'])

    def test_model_skipped_a_word_is_aligned(self):
        with answer(['Shark', 'ne', 'dekh', 'liya.']):
            out, n = capfix.fix(words('shaark ne hame dekh liya'), model='x')
        self.assertEqual([w['text'] for w in out], ['Shark', 'ne', 'hame', 'dekh', 'liya.'])

    def test_wrong_count_or_error_keeps_words(self):
        with answer(['zzz', 'qqq']):
            self.assertEqual(capfix.fix(words('a b c'), model='x')[0], words('a b c'))
        with mock.patch('llm.complete', side_effect=TimeoutError):
            self.assertEqual(capfix.fix(words('a b c'), model='x'), (words('a b c'), 0))

    def test_title_case_everything_is_undone(self):
        with answer(['Bhai', 'Ye', 'Lamborghini', 'Dekho', '11', 'Lakh', 'Ki', 'Hai']):
            out, _ = capfix.fix(words('bhai ye lamborgini dekho eleven lakh ki hai'), model='x')
        self.assertEqual([w['text'] for w in out], ['Bhai', 'ye', 'Lamborghini', 'dekho', '11', 'lakh', 'ki', 'hai'])

    def test_echoed_numbers_removed_real_numbers_kept(self):
        with answer(['0: Ek', '1: gun', '2: 1.']):
            out, _ = capfix.fix(words('ek gun 1.'), model='x')
        self.assertEqual([w['text'] for w in out], ['Ek', 'gun', '1.'])

    def test_no_model_no_change(self):
        with mock.patch('smart._model', return_value=None):
            self.assertEqual(capfix.fix(words('a b c')), (words('a b c'), 0))


if __name__ == '__main__':
    unittest.main()

