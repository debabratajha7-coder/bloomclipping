import subprocess, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import frozen


def make(path, moving):
    src = 'testsrc2=s=320x180:d=8' if moving else 'testsrc2=s=320x180:d=1,trim=end_frame=1,loop=loop=240:size=1:start=0,setpts=N/30/TB'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', src, '-t', '8', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(path)], check=True)


class Frozen(unittest.TestCase):
    def test_still_slate_is_frozen_moving_is_not(self):
        with tempfile.TemporaryDirectory() as d:
            still, live = Path(d) / 'still.mp4', Path(d) / 'live.mp4'
            make(still, False); make(live, True)
            self.assertTrue(frozen.is_frozen(still, 0, 8)[0])
            self.assertFalse(frozen.is_frozen(live, 0, 8)[0])

    def test_unreadable_file_is_not_dropped(self):
        self.assertEqual(frozen.is_frozen('missing.mp4', 0, 5), (False, None))


if __name__ == '__main__':
    unittest.main()
