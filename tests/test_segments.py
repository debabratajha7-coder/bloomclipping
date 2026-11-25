"""Cutting a clip from several pieces of the saved video."""
import shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import segments


class ValidateTests(unittest.TestCase):
    def test_good_and_bad_pieces(self):
        self.assertEqual(segments.validate([{'start': 1, 'end': 3}, {'start': 5, 'end': 9}], 20), [(1.0, 3.0), (5.0, 9.0)])
        for bad in ([], 'x', [{'start': 0, 'end': 1}], [{'start': -1, 'end': 9}], [{'start': 0, 'end': 99}], [{'start': 'a', 'end': 4}], [{'start': 5, 'end': 5.1}] * 3,
                    [{'start': 0, 'end': 4}] * 17):
            with self.assertRaises(ValueError, msg=str(bad)):
                segments.validate(bad, 20)

    def test_same_pieces_same_id(self):
        self.assertEqual(segments.derived_id('abc', [(1, 2)]), segments.derived_id('abc', [(1, 2)]))
        self.assertNotEqual(segments.derived_id('abc', [(1, 2)]), segments.derived_id('abc', [(1, 3)]))

    def test_graph_joins_in_order(self):
        g = segments.graph([(5, 8), (0, 2)], True)
        self.assertLess(g.index('trim=5:8'), g.index('trim=0:2'))
        self.assertIn('concat=n=2:v=1:a=1', g)
        self.assertIn('concat=n=1:v=1:a=0', segments.graph([(0, 3)], False))


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg needed')
class BuildTests(unittest.TestCase):
    def test_joined_file_has_the_total_length(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc=size=160x90:rate=15:duration=10', '-f', 'lavfi', '-i', 'sine=duration=10',
                            '-shortest', '-pix_fmt', 'yuv420p', str(d / 'abc.mp4')], check=True)
            sid = segments.build(d, 'abc', [(1.0, 3.0), (6.0, 9.0)])
            out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(d / (sid + '.mp4'))], capture_output=True, text=True).stdout
            self.assertAlmostEqual(float(out), 5.0, delta=0.3)
            self.assertEqual(segments.build(d, 'abc', [(1.0, 3.0), (6.0, 9.0)]), sid)


if __name__ == '__main__':
    unittest.main()
