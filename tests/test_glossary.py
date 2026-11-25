import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import glossary
from translit import roman_text, to_hinglish


def words(text):
    return [{'start': i * .5, 'end': i * .5 + .4, 'text': w} for i, w in enumerate(text.split())]


class Hinglish(unittest.TestCase):
    def test_chat_style_spelling(self):
        got = ' '.join(to_hinglish(w) for w in 'मैं वहाँ जा रहा हूँ पुलिस भाई सच्चा शायद'.split())
        self.assertEqual(got, 'main wahan ja raha hoon police bhai saccha shayad')

    def test_two_letter_words_keep_long_vowel(self):
        self.assertEqual(to_hinglish('आ'), 'aa')

    def test_mixed_hook_becomes_roman(self):
        self.assertEqual(roman_text('Shark ने हमें देख लिया?!'), 'Shark ne hame dekh liya?!')

    def test_english_untouched(self):
        self.assertEqual(roman_text('Police chase in Vice City'), 'Police chase in Vice City')


class Glossary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); glossary.setup(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_and_fix_keeps_timing_and_punctuation(self):
        glossary.add('endi', 'Andy')
        out = glossary.fix_words(words('ye endi, hai kaun'))
        self.assertEqual([w['text'] for w in out], ['ye', 'Andy,', 'hai', 'kaun'])
        self.assertEqual(out[1]['start'], .5)

    def test_case_insensitive_and_devanagari(self):
        glossary.add('एंडी', 'Andy')
        glossary.add('PULIS', 'police')
        self.assertEqual([w['text'] for w in glossary.fix_words(words('एंडी pulis!'))], ['Andy', 'police!'])

    def test_hindi_full_stop_is_punctuation(self):
        glossary.add('एंडी', 'Andy')
        self.assertEqual([w['text'] for w in glossary.fix_words(words('एंडी। एंडी?'))], ['Andy।', 'Andy?'])

    def test_phrase_entry_merges_words(self):
        glossary.add('vice siti', 'Vice City')
        out = glossary.fix_words(words('welcome to vice siti bhai'))
        self.assertEqual([w['text'] for w in out], ['welcome', 'to', 'Vice City', 'bhai'])
        self.assertEqual((out[2]['start'], out[2]['end']), (1.0, 1.9))

    def test_whole_word_only(self):
        glossary.add('car', 'gaadi')
        self.assertEqual([w['text'] for w in glossary.fix_words(words('cartoon car'))], ['cartoon', 'gaadi'])

    def test_replace_and_remove(self):
        glossary.add('endi', 'Andi'); glossary.add('endi', 'Andy')
        self.assertEqual(glossary.entries(), [{'from': 'endi', 'to': 'Andy'}])
        glossary.remove('ENDI')
        self.assertEqual(glossary.entries(), [])

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError): glossary.add('', 'x')
        with self.assertRaises(ValueError): glossary.add('a b c d', 'x')

    def test_fix_text(self):
        glossary.add('endi', 'Andy')
        self.assertEqual(glossary.fix_text('Who is endi?!'), 'Who is Andy?!')


if __name__ == '__main__':
    unittest.main()
