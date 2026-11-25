import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

import campaign_deals as deals


def html(source):
    return BeautifulSoup(source, "html.parser")


class CampaignDealsTest(unittest.TestCase):
    def detail(self, facts):
        page = html('<img src="https://crusercontent.com/org/campaigns/thumbnails/cover.webp">'
                    '<span>Organizer</span><h1>Example GTA campaign</h1>' +
                    "".join("<p>" + value + "</p>" for value in facts))
        return patch.object(deals, "page", return_value=page)

    def test_accepting_pool_uses_individual_campaign_amount(self):
        facts = ["Accepting clips", "Pool", "Pool", "$12,500.00", "Split by", "Views"]
        with self.detail(facts):
            offer = deals.details(("/c/campaigns/example", "pool"))
        self.assertEqual(offer["amount"], 12500)
        self.assertTrue(offer["shared_by_views"])
        self.assertTrue(offer["poster"].endswith("cover.webp"))

    def test_rate_and_budget_are_distinct(self):
        facts = ["Accepting clips", "Per 1K views", "$3", "Per 1K views", "Up to", "$4",
                 "Budget", "$900", "/", "$4,000"]
        with self.detail(facts):
            offer = deals.details(("/c/campaigns/example", "rate"))
        self.assertEqual((offer["minimum"], offer["amount"], offer["budget"]), (3, 4, 4000))
        self.assertTrue(offer["variable"])

    def test_closed_campaign_is_omitted(self):
        with self.detail(["Campaign ended", "Pool", "Pool", "$15,000"]):
            self.assertIsNone(deals.details(("/c/campaigns/example", "pool")))
