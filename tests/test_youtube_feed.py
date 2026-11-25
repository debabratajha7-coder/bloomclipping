import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import FastAPI

import creators
from youtube_feed import DAY, LIVE_MAX_AGE, normalize_entries, ranked_feed, youtube_watchlist


class YouTubeFeedTests(unittest.TestCase):
    def test_streams_distinguish_live_replays_and_upcoming(self):
        listing = {"channel": "Channel", "entries": [
            {"id": "livevideo01", "title": "Live", "live_status": "is_live", "concurrent_view_count": 80},
            {"id": "replayvid01", "title": "Replay", "live_status": "was_live", "view_count": 250},
            {"id": "upcoming001", "title": "Later", "live_status": "is_upcoming"},
            {"id": "shortvideo1", "title": "Short", "url": "https://www.youtube.com/shorts/shortvideo1"},
            {"id": "videoid0001", "title": "Upload"},
        ]}
        answers = normalize_entries(listing, "Channel", "streams")
        self.assertEqual(["Live", "Replay"], [row["title"] for row in answers])
        self.assertEqual([80, 250], [row["views"] for row in answers])
        self.assertTrue(answers[0]["live"])
        self.assertTrue(answers[1]["replay"])
        self.assertEqual(3, len(normalize_entries(listing, "Channel", "videos")))

    def test_expired_live_indications_and_recent_popularity(self):
        now = 100 * DAY
        live = {"id": "live", "live": True, "views": 80}
        new = {"id": "new", "live": False, "published": now - DAY, "views": 200, "replay": False}
        hot = {"id": "hot", "live": False, "published": now - 2 * DAY, "views": 2000, "replay": False}
        old = {"id": "old", "live": False, "published": now - 40 * DAY, "views": 7000, "replay": True}
        snapshot = {"a": {"checked": now - LIVE_MAX_AGE - 1, "entries": [live]},
                    "b": {"checked": now, "entries": [new, hot, old]}}
        feed = ranked_feed(snapshot, now)
        self.assertEqual([], feed["live"])
        self.assertEqual(["new", "hot"], [row["id"] for row in feed["latest"]])
        self.assertEqual(["hot", "new"], [row["id"] for row in feed["popular"]])
        self.assertIn(old, ranked_feed(snapshot, now, include_older=True)["latest"])

    def test_saved_youtube_creators_extend_default_watchlist(self):
        channels, saved = youtube_watchlist([
            {"ref": "@GamerFleet", "platform": "youtube"},
            {"ref": "@MyNewChannel", "platform": "youtube", "auto": False},
            {"ref": "twitchuser", "platform": "twitch", "auto": True},
        ])
        self.assertEqual({"@gamerfleet", "@mynewchannel"}, set(saved))
        self.assertEqual("@MyNewChannel", channels["@mynewchannel"])
        self.assertEqual("@GamerFleet", channels["@gamerfleet"])
        self.assertNotIn("twitchuser", channels)

    def test_feed_saved_creator_starts_recording_only_when_enabled(self):
        workers = []

        def capture_worker(target, daemon, name=None):
            worker = Mock()
            if name != "creator-watcher":
                workers.append(target)
            return worker

        with tempfile.TemporaryDirectory() as folder:
            app = FastAPI()
            record = Mock(return_value="session")
            with patch.object(creators.threading, "Thread", side_effect=capture_worker), \
                 patch.object(creators, "live_target", return_value=("youtube", "id", "url")):
                creators.attach(app, Path(folder), {}, record)
                routes = {route.path: route.endpoint for route in app.routes}
                cid = routes["/creators"]({"url": "https://www.youtube.com/@Sample", "auto": False})["id"]
                workers.pop()()
                self.assertFalse(creators.read_store(folder)[0]["auto"])
                record.assert_not_called()
                routes["/creators/{cid}/auto"](cid, {"auto": True})
                workers.pop()()
                record.assert_called_once_with(("youtube", "id", "url"), {}, cid)
                routes["/creators/{cid}/auto"](cid, {"auto": True})
                routes["/creators/{cid}/auto"](cid, {"auto": False})
                workers.pop()()
                self.assertEqual(1, record.call_count)
