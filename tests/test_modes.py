import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import modes, llm


class Modes(unittest.TestCase):
    def test_fast_is_light(self):
        f = modes.resolve('fast')
        self.assertTrue(f['hinglish'] and f['chat_replay'] and f['rerank'])
        self.assertFalse(f['caption_fix'] or f['whole_pass'] or f['deep_scan'] or f['fair_order'])

    def test_balanced_and_best(self):
        self.assertTrue(modes.resolve('balanced')['caption_fix'] and not modes.resolve('balanced')['deep_scan'])
        best=modes.resolve('deep')
        self.assertTrue(all(value for key,value in best.items() if key not in ('facecam_check','face_reaction')))
        self.assertFalse(best['facecam_check'])
        self.assertFalse(best['face_reaction'])
        self.assertTrue(modes.resolve('deep',{'face_reaction':True})['face_reaction'])

    def test_tiles_override_and_junk_ignored(self):
        f = modes.resolve('fast', {'whole_pass': True, 'chat_replay': False, 'nope': True, 'rerank': 'yes'})
        self.assertTrue(f['whole_pass']); self.assertFalse(f['chat_replay']); self.assertNotIn('nope', f); self.assertTrue(f['rerank'])
        self.assertEqual(modes.resolve('weird'), modes.resolve('fast'))

    def test_catalog_and_presets(self):
        c = modes.catalog()
        self.assertEqual([m['key'] for m in c['modes']], ['fast', 'balanced', 'deep'])
        self.assertTrue(all(f['load'] in ('light', 'medium', 'heavy') for f in c['features']))
        for k in ('groq', 'gemini', 'nvidia', 'xai'):
            self.assertTrue(llm.PRESETS[k]['key_url'].startswith('https://'))


if __name__ == '__main__':
    unittest.main()
