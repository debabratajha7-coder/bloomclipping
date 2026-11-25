import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import replay, learn


def heat(duration, peak_at, n=100):
    step = duration / n
    rows = []
    for i in range(n):
        a = i * step
        v = 1.0 if i == 0 else (0.3 + (0.6 if abs(a - peak_at) < step * 2 else 0) - i * .001)
        rows.append({'start_time': a, 'end_time': a + step, 'value': v})
    return rows


class Replay(unittest.TestCase):
    def test_peak_found_opening_ignored(self):
        sig = replay.per_second(replay.from_info({'heatmap': heat(600, 400)}), 600)
        self.assertLess(abs(int(sig.argmax()) - 400), 15)
        self.assertEqual(float(sig[:20].max()), 0.0)
        self.assertGreater(replay.window(sig, 390, 420), .9)
        self.assertLess(replay.window(sig, 100, 130), .2)

    def test_no_heatmap(self):
        self.assertIsNone(replay.from_info({}))
        self.assertIsNone(replay.per_second(None, 600))

    def test_learning_knows_replay(self):
        self.assertIn('replay', learn.FEATURES)
        self.assertGreater(learn.score({'replay': 1.0, 'llm': .5}, learn.DEFAULT), learn.score({'replay': 0.0, 'llm': .5}, learn.DEFAULT))


if __name__ == '__main__':
    unittest.main()
