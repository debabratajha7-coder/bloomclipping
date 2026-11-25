import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import intent


class ExactTime(unittest.TestCase):
    def moments(self, text):
        return [(m['start'], m['end'], m['snap']) for m in intent.explicit(text, 30, 60)]

    def test_range_is_cut_as_written(self):
        for text in ('1:35:00 to 1:36:00', '1:35:00-1:36:00', '95:00 - 96:00', '1:35:00 se 1:36:00 tak', 'from 01:35:00 till 01:36:00'):
            self.assertEqual(self.moments(text), [(5700.0, 5760.0, False)], text)

    def test_single_time_starts_there_with_usual_length(self):
        for text in ('1:35:00', 'clip at 1:35:00', '5700s', '1h35m', '1 hour 35 min', 'minute 95', '1:35:00 wala moment'):
            self.assertEqual(self.moments(text), [(5699.7, 5744.7, True)], text)

    def test_units_are_added_not_split(self):
        self.assertEqual(intent.seconds('1h 35m 20s'), 5720)
        self.assertEqual(intent.seconds('1 hour 35 min'), 5700)
        self.assertEqual(intent.seconds('90s'), 90)

    def test_topic_or_style_keeps_hint_behaviour(self):
        for text in ('funny moment around 1:35:00', 'police chase 1:35:00 to 1:36:00', 'when he talks about the heist 1:35:00'):
            self.assertEqual(self.moments(text), [], text)
            self.assertTrue(intent.parse(text, 7000)['spans'], text)

    def test_two_times_two_clips_and_long_range_capped(self):
        self.assertEqual(len(self.moments('1:35:00 aur 1:50:00')), 2)
        self.assertEqual(self.moments('1:00:00 to 1:30:00'), [(3600.0, 3780.0, False)])

    def test_nothing_asked(self):
        self.assertEqual(self.moments(''), [])
        self.assertEqual(self.moments('best moments please'), [])


class WindowFinder(unittest.TestCase):
    def test_inside(self):
        self.assertEqual(intent.inside({'start': 100, 'end': 130}, [(90, 200)]), 1.0)
        self.assertEqual(intent.inside({'start': 300, 'end': 330}, [(90, 200)]), 0.0)


if __name__ == '__main__':
    unittest.main()
