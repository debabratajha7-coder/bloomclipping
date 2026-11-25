import unittest
from unittest.mock import patch

import scene_edges


class SceneEdges(unittest.TestCase):
    def test_adjusts_edges_only_in_silence(self):
        words = [{"start": .7, "end": 8.4}]
        with patch.object(scene_edges, "hard_cuts", side_effect=[[2.35, 2.5], [11.1, 11.5]]) as read:
            self.assertEqual((2.5, 11.1), scene_edges.align("source", 2, 12, words, 8))
        self.assertLess(read.call_args_list[0].args[-1], 2.7)
        self.assertGreater(read.call_args_list[1].args[-2], 10.4)

    def test_never_reads_edges_when_there_is_no_safe_speech_gap(self):
        words = [{"start": .03, "end": 9.95}]
        with patch.object(scene_edges, "hard_cuts") as read:
            self.assertEqual((2, 12), scene_edges.align("source", 2, 12, words, 8))
            read.assert_not_called()

    def test_tail_never_makes_clip_shorter_than_requested_minimum(self):
        words = [{"start": .6, "end": 8.4}]
        with patch.object(scene_edges, "hard_cuts", side_effect=[[2.45], [11.3, 11.6]]):
            self.assertEqual((2.45, 11.6), scene_edges.align("source", 2, 12, words, 9))
