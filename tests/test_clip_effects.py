import unittest

import clip_effects


class ClipEffects(unittest.TestCase):
    def test_masks_spoken_words_with_punctuation_at_saved_times(self):
        mode, picked = clip_effects.settings({"censor_mode": "bleep", "censor_words": "Damn, गाली"})
        words = [{"start": 0, "end": .3, "text": "Damn!"}, {"start": .4, "end": .7, "text": "well"},
                 {"start": .8, "end": 1.4, "text": "गाली।"}]
        masked, spans = clip_effects.masked_words(words, picked, 1.4)
        self.assertEqual(["****", "well", "****"], [word["text"] for word in masked])
        self.assertEqual(mode, "bleep")
        self.assertEqual(0, spans[0][0])
        self.assertEqual(1.4, spans[-1][-1])
        self.assertEqual("Damn!", words[0]["text"])

    def test_invalid_sizes_and_modes_are_rejected(self):
        with self.assertRaises(ValueError):
            clip_effects.settings({"censor_mode": "unknown"})
        with self.assertRaises(ValueError):
            clip_effects.settings({"censor_words": ["word"]})
