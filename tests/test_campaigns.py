import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, HTTPException

import campaigns


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.data = Path(self.folder.name)
        self.catalog = self.data / "directory.json"
        self.catalog.write_text(json.dumps({"platforms": [
            {"id": "invalid", "name": "Bad", "referral_url": "javascript:alert(1)"},
            {"id": "direct", "name": "Direct", "url": "https://example.org/campaigns",
             "referral_url": "http://example.org/ref", "note": "a" * 300, "private": "ignored"},
            {"id": "partner", "name": "Partner", "referral_url": "https://example.org/join?ref=owner",
             "note": "a" * 300, "private": "ignored"},
            {"id": "other", "name": "Other", "referral_url": "https://example.org/other?ref=owner"},
        ]}), encoding="utf-8")
        catalog = patch.object(campaigns, "CATALOG", self.catalog)
        catalog.start()
        self.addCleanup(catalog.stop)
        app = FastAPI()
        campaigns.attach(app, self.data)
        self.routes = {route.path: route.endpoint for route in app.routes}

    def test_bad_urls_and_unknown_fields_are_dropped(self):
        rows = self.routes["/campaigns"]()["platforms"]
        self.assertEqual(["partner", "other"], [row["id"] for row in rows])
        self.assertNotIn("private", rows[0])
        self.assertEqual(220, len(rows[0]["note"]))
        for url in ("https:///missing-host", "https://a.test\\@b.test",
                    "https://name:pass@a.test", "https://a.test/\t/path"):
            self.assertEqual("", campaigns.https_url(url))

    def test_open_returns_affiliate_link_and_sorts_by_local_totals(self):
        open_campaign = self.routes["/campaigns/open"]
        self.assertEqual({"url": "https://example.org/join?ref=owner"},
                         open_campaign(campaigns.CampaignOpen(id="partner")))
        for _ in range(2):
            self.assertEqual({"url": "https://example.org/other?ref=owner"},
                             open_campaign(campaigns.CampaignOpen(id="other")))
        self.assertEqual({"partner": 1, "other": 2},
                         campaigns.read_counts(self.data / "campaign-clicks.json"))
        self.assertEqual("other", self.routes["/campaigns"]()["platforms"][0]["id"])
        with self.assertRaises(HTTPException) as error:
            open_campaign(campaigns.CampaignOpen(id="direct"))
        self.assertEqual(404, error.exception.status_code)
