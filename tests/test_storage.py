"""Storage panel: what can be cleaned, what is protected, choosing another folder."""
import json, os, sys, tempfile, time, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import storage

A, B, C, D = 'a' * 32, 'b' * 32, 'c' * 32, 'd' * 32       # clip, its source, an unused source, a job folder


def age(path, seconds):
    t = time.time() - seconds
    os.utime(path, (t, t))


def put(path, size=1000, old=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'x' * size)
    if old:
        age(path, 7200)
    return path


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        # one finished clip (A) made from source B, an unused source C, junk
        put(self.d / (A + '.mp4'), 5000)
        put(self.d / (A + '.ass'), 10)
        (self.d / (A + '.json')).write_text(json.dumps({'source': B, 'settings': {}, 'result': {'status': 'done'}}), encoding='utf-8')
        age(self.d / (A + '.json'), 7200)
        put(self.d / (B + '.mp4'), 9000)
        put(self.d / (C + '.mp4'), 7000)
        age(self.d / (C + '.mp4'), 2 * 86400)
        put(self.d / 'x.audio.m4a', 3000)
        put(self.d / D / 'source.mp4.part', 4000)
        put(self.d / ('f' * 32 + '-preview') / '0.jpg', 100)
        put(self.d / 'live_abc' / 'rec.ts', 8000)
        put(self.d / 'models' / 'big.bin', 20000)

    def tearDown(self):
        self.tmp.cleanup()

    def names(self, action, **kw):
        return {f.name for f in storage.plan(self.d, action, **kw)['files']}

    def test_temp_lists_partial_audio_and_previews_but_never_clips_or_models(self):
        n = self.names('temp')
        self.assertIn('x.audio.m4a', n)
        self.assertIn(D, n)
        self.assertIn('f' * 32 + '-preview', n)
        self.assertNotIn(A + '.mp4', n)
        self.assertNotIn('big.bin', n)

    def test_orphans_vs_sources_of_clips(self):
        self.assertEqual(self.names('orphans'), {C + '.mp4'})
        self.assertEqual(self.names('sources'), {B + '.mp4'})

    def test_recent_files_are_never_listed(self):
        put(self.d / 'y.audio.m4a', 500, old=False)
        put(self.d / ('e' * 32 + '.mp4'), 500, old=False)
        self.assertNotIn('y.audio.m4a', self.names('temp'))
        self.assertNotIn('e' * 32 + '.mp4', self.names('orphans'))

    def test_recordings_need_to_be_an_hour_old(self):
        self.assertEqual(self.names('recordings'), {'live_abc'})
        age(self.d / 'live_abc' / 'rec.ts', 60)
        self.assertEqual(self.names('recordings'), set())

    def test_old_clips_lists_every_file_of_the_clip(self):
        age(self.d / (A + '.mp4'), 3 * 86400)                # the clip is three days old
        self.assertEqual(self.names('old_clips', days=1), {A + '.mp4', A + '.ass', A + '.json'})
        self.assertEqual(self.names('old_clips', days=30), set())

    def test_apply_frees_space_and_keeps_the_rest(self):
        before = storage.plan(self.d, 'orphans')['bytes']
        result = storage.apply(self.d, 'orphans')
        self.assertEqual(result['freed'], before)
        self.assertFalse((self.d / (C + '.mp4')).exists())
        self.assertTrue((self.d / (A + '.mp4')).exists())
        self.assertTrue((self.d / (B + '.mp4')).exists())

    def test_summary_numbers(self):
        s = storage.summary(self.d)
        self.assertEqual(s['clips']['count'], 1)
        self.assertGreater(s['models'], 0)
        self.assertGreater(s['actions']['temp']['bytes'], 0)
        self.assertGreater(s['free'], 0)

    def test_unknown_action_is_refused(self):
        with self.assertRaises(ValueError):
            storage.plan(self.d, 'everything')

    def test_nothing_outside_the_data_folder_is_listed(self):
        outside = Path(tempfile.mkdtemp())
        try:
            self.assertFalse(storage._inside(self.d, outside))
            self.assertTrue(storage._inside(self.d, self.d / 'sub' / 'file'))
        finally:
            outside.rmdir()

    def test_folder_choice_validation_and_saving(self):
        for bad in ('', 'relative/path', 'x' * 500):
            with self.assertRaises(ValueError):
                storage.validate_folder(bad)
        target = self.d / 'new place'
        root = self.d / 'app'
        root.mkdir()
        saved = storage.save_folder(root, str(target))
        self.assertTrue(Path(saved).is_dir())
        self.assertEqual(Path(storage.configured_folder(root)), Path(saved))
        storage.save_folder(root, '')                       # empty = back to the default
        self.assertEqual(storage.configured_folder(root), '')


if __name__ == '__main__':
    unittest.main()


class SafetyTests(StorageTests):
    def test_a_source_from_today_is_not_called_unused(self):
        put(self.d / ('9' * 32 + '.mp4'), 500)                 # two hours old: still might be open in the editor
        self.assertNotIn('9' * 32 + '.mp4', self.names('orphans'))


class DeleteClipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.clips = ['1' * 32, '2' * 32]
        self.src = '3' * 32
        for c in self.clips:
            put(self.d / (c + '.mp4'), 4000)
            put(self.d / (c + '.ass'), 10)
            (self.d / (c + '.json')).write_text(json.dumps({'source': self.src, 'settings': {}, 'result': {'status': 'done'}}), encoding='utf-8')
        put(self.d / (self.src + '.mp4'), 9000)

    def tearDown(self):
        self.tmp.cleanup()

    def test_deletes_only_the_chosen_clip_and_keeps_a_shared_source(self):
        r = storage.delete_clips(self.d, [self.clips[0]], with_sources=True)
        self.assertEqual(r['deleted'], 1)
        self.assertFalse((self.d / (self.clips[0] + '.mp4')).exists())
        self.assertFalse((self.d / (self.clips[0] + '.ass')).exists())
        self.assertTrue((self.d / (self.clips[1] + '.mp4')).exists())
        self.assertTrue((self.d / (self.src + '.mp4')).exists(), 'another clip still uses this source')
        self.assertEqual(r['sources'], 0)

    def test_source_goes_when_the_last_clip_using_it_goes(self):
        r = storage.delete_clips(self.d, self.clips, with_sources=True)
        self.assertEqual(r['deleted'], 2)
        self.assertEqual(r['sources'], 1)
        self.assertFalse((self.d / (self.src + '.mp4')).exists())
        self.assertGreater(r['freed'], 17000)

    def test_source_is_kept_unless_asked(self):
        storage.delete_clips(self.d, self.clips)
        self.assertTrue((self.d / (self.src + '.mp4')).exists())

    def test_unknown_or_bad_ids_are_ignored(self):
        r = storage.delete_clips(self.d, ['../x', 'f' * 32, 5, None, self.src])
        self.assertEqual(r['deleted'], 0)
        self.assertTrue((self.d / (self.src + '.mp4')).exists())
