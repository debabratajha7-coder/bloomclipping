import json, os, sys, tempfile, time, unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import automation


class Queue:
    def __init__(self): self.items = []
    def enqueue(self, kind, payload, when): self.items.append((kind, payload)); return {'id': 'x'}


class Automation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.data = Path(self.tmp.name) / 'data'; self.data.mkdir()
        self.watch = Path(self.tmp.name) / 'rec'; self.watch.mkdir(); self.q = Queue()
        automation._ctx.update(data=self.data, probe=lambda p: {'duration': 60}, queue=lambda: self.q, seen={}, status='off', last='')

    def tearDown(self): self.tmp.cleanup()

    def test_banned_words_whole_word_any_case(self):
        self.assertEqual(automation.lint(['Holy SHIT bro', 'classic'], ['shit', 'ass']), ['shit'])
        self.assertEqual(automation.lint(['a classy assistant'], ['ass']), [])

    def test_settings_validation(self):
        with self.assertRaises(ValueError): automation.save(self.data, {'webhook_url': 'http://evil.example.com/x'})
        with self.assertRaises(ValueError): automation.save(self.data, {'watch_folder': str(self.watch / 'nope')})
        with self.assertRaises(ValueError): automation.save(self.data, {'watch_on': True})
        cfg = automation.save(self.data, {'watch_folder': str(self.watch), 'watch_on': True, 'banned': 'a, b\nc', 'webhook_url': 'https://discord.com/api/webhooks/1/x'})
        self.assertEqual(cfg['banned'], ['a', 'b', 'c']); self.assertTrue(automation.read()['watch_on'])

    def test_watch_folder_takes_a_finished_file_once(self):
        automation.save(self.data, {'watch_folder': str(self.watch), 'watch_on': True, 'watch_count': 3})
        f = self.watch / 'stream.mp4'; f.write_bytes(b'0' * 300_000)
        old = time.time() - 120; os.utime(f, (old, old))
        automation._scan_once(); self.assertEqual(self.q.items, [])          # first sight: wait for a quiet poll
        automation._scan_once(); self.assertEqual(len(self.q.items), 1)      # size unchanged and old enough: taken
        automation._scan_once(); self.assertEqual(len(self.q.items), 1)      # never twice
        kind, payload = self.q.items[0]
        self.assertEqual((kind, payload['count'], payload['mode']), ('make', 3, 'fast'))
        self.assertTrue((self.data / (payload['id'] + '.mp4')).exists())

    def test_growing_file_and_non_video_ignored(self):
        automation.save(self.data, {'watch_folder': str(self.watch), 'watch_on': True})
        f = self.watch / 'live.mkv'; f.write_bytes(b'0' * 300_000)
        automation._scan_once(); f.write_bytes(b'0' * 400_000); automation._scan_once()
        self.assertEqual(self.q.items, [])
        (self.watch / 'notes.txt').write_text('x'); automation._scan_once(); self.assertEqual(self.q.items, [])

    def test_webhook_sends_small_json_only(self):
        automation.save(self.data, {'webhook_url': 'https://example.com/hook'})
        sent = []
        class R:
            def read(self, n): return b''
        with mock.patch('urllib.request.urlopen', side_effect=lambda req, timeout=0: sent.append(json.loads(req.data)) or R()):
            automation.notify(self.data, {'title': 'T', 'hook': 'H', 'score': 70, 'file': 'abc', 'secret': 'no'})
            time.sleep(.3)
        self.assertEqual(sent[0]['title'], 'T'); self.assertNotIn('secret', sent[0])


if __name__ == '__main__':
    unittest.main()
