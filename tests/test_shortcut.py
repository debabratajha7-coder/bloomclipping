import os, platform, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import shortcut


class Shortcut(unittest.TestCase):
    @unittest.skipUnless(platform.system() == 'Windows', 'Windows shortcut')
    def test_desktop_and_start_menu_in_a_temp_profile(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d); (home / 'Desktop').mkdir(); start = home / 'Roaming' / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs'; start.mkdir(parents=True)
            with mock.patch.dict(os.environ, {'USERPROFILE': str(home), 'APPDATA': str(home / 'Roaming')}):
                r = shortcut.create()
            self.assertEqual(len(r['made']), 2)
            self.assertTrue((home / 'Desktop' / 'BloomClipping.lnk').exists())
            self.assertTrue((shortcut.ROOT / 'open.ps1').exists())

    def test_manifest_installable(self):
        m = shortcut.manifest()
        self.assertEqual((m['start_url'], m['display']), ('/', 'standalone'))
        self.assertTrue(m['icons'])


if __name__ == '__main__':
    unittest.main()
