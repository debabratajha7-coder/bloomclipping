import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import intent


class Direction(unittest.TestCase):
    def test_explicit_number_of_clips_overrides_the_picker(self):
        self.assertEqual(5,intent.requested_count('5 funny clips. Return 5 clips near the end.',4))
        self.assertEqual(12,intent.requested_count('20 clips banao',4))
        self.assertEqual(4,intent.requested_count('around 5 minutes',4))
    def test_times_ranges_and_words(self):
        d = intent.parse('funny moments first, more from around 1:35:00, 10:00-12:00 and the chase near the end', 7200)
        self.assertIn((5640.0, 5760.0), d['spans'])
        self.assertIn((600.0, 720.0), d['spans'])
        self.assertIn((6120.0, 7200.0), d['spans'])
        self.assertEqual(d['styles'], {'humour', 'action'})

    def test_hinglish(self):
        d = intent.parse('1:35 ke paas wala, hasi wale clips, shuru mein bhi', 600)
        self.assertIn((35.0, 155.0), d['spans'])
        self.assertIn((0.0, 90.0), d['spans'])
        self.assertIn('humour', d['styles'])

    def test_minutes_words(self):
        self.assertIn((2640.0, 2760.0), intent.parse('around 45 minutes', 3600)['spans'])

    def test_boost(self):
        d = {'spans': [(100, 160)], 'styles': {'humour'}}
        self.assertAlmostEqual(intent.boost({'start': 100, 'end': 130, 'kind': 'humour'}, d), .33)
        self.assertEqual(intent.boost({'start': 300, 'end': 330, 'kind': 'action'}, d), 0)

    def test_nothing_asked(self):
        self.assertEqual(intent.parse('', 600), {'spans': [], 'styles': set()})


if __name__ == '__main__':
    unittest.main()
