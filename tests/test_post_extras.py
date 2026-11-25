import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import smart, captions


class PostExtras(unittest.TestCase):
    def test_only_spoken_punch_words_clean_tags_no_links(self):
        out = smart.post_extras({'highlight_words': ['POLICE!', 'helicopter', 'bhaago', 'police'],
                                 'hashtags': ['#GTA6', 'Vice City', 'gta6', 'chase!'],
                                 'description': 'Wild chase, visit www.example.com or @someone now.\n'},
                                'arre bhaago police aa gayi')
        self.assertEqual(out['highlight_words'], ['police', 'bhaago'])
        self.assertEqual(out['hashtags'], ['GTA6', 'ViceCity', 'chase'])
        self.assertEqual(out['description'], 'Wild chase, visit or now.')

    def test_missing_fields(self):
        self.assertEqual(smart.post_extras({}, 'x'), {'highlight_words': [], 'hashtags': [], 'description': ''})


class PunchWordsInCaptions(unittest.TestCase):
    def test_punch_word_keeps_active_colour(self):
        words = [{'start': i * .5, 'end': i * .5 + .4, 'text': t} for i, t in enumerate('arre bhaago police aa gayi'.split())]
        with tempfile.TemporaryDirectory() as d:
            captions.write(words, 'karaoke', Path(d), 'x', appearance={'punch_words': ['police']})
            ass = (Path(d) / 'x.ass').read_text(encoding='utf-8')
        active = captions.STYLES['karaoke'][1]
        first = [l for l in ass.splitlines() if l.startswith('Dialogue') and 'ARRE' in l][0]
        self.assertIn('\\c' + active + '}POLICE', first)          # police highlighted while 'arre' is spoken


if __name__ == '__main__':
    unittest.main()
