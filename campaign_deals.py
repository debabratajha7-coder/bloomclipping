"""Featured offers from the public Content Rewards board."""

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

SITE = "https://contentrewards.com"
CAMPAIGN = re.compile(r"/c/campaigns/[0-9a-f-]{36}")
MONEY = re.compile(r"\$([\d,]+(?:\.\d+)?)([KM]?)")
GAME = re.compile(r"\bgta\b|grand theft auto|\bgaming\b|\bsega\b|\bfaze\b", re.I)
BIDI = dict.fromkeys(map(ord, "\u2066\u2067\u2068\u2069"))
LOG = logging.getLogger(__name__)


def dollars(value):
    return [float(number.replace(",", "")) * {"": 1, "K": 1000, "M": 1000000}[unit]
            for number, unit in MONEY.findall(value)]


def poster(soup):
    for image in soup.find_all("img", src=True):
        src = urlsplit(image["src"])
        if (src.scheme == "https" and src.netloc == "crusercontent.com"
                and "/campaigns/thumbnails/" in src.path):
            return src.geturl()
    return ""


def page(path):
    response = requests.get(SITE + path, timeout=(4, 7), allow_redirects=False)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def candidates(soup):
    seen = set()
    offers = {"pool": [], "rate": []}
    for anchor in soup.find_all("a", href=True):
        path = anchor["href"].split("?", 1)[0]
        label = anchor.get("aria-label", "")
        if not CAMPAIGN.fullmatch(path) or not label.startswith("Preview ") or path in seen:
            continue
        values = [value.translate(BIDI) for value in anchor.stripped_strings]
        if len(values) < 5:
            continue
        seen.add(path)
        title = label[8:]
        if values[-1].endswith(" pool"):
            amounts = dollars(values[-1])
            if amounts and amounts[0] >= 5000:
                offers["pool"].append((path, bool(GAME.search(title)), amounts[0]))
        elif values[-1] == "/1K":
            rates = dollars(values[-2])
            if rates and max(rates) >= 2:
                offers["rate"].append((path, bool(GAME.search(title)), max(rates)))
    pools = sorted(offers["pool"], key=lambda row: (row[1], row[2]), reverse=True)[:5]
    rates = sorted(offers["rate"], key=lambda row: row[2], reverse=True)[:5]
    return [(row[0], kind) for kind, rows in (("pool", pools), ("rate", rates)) for row in rows]


def details(candidate):
    path, kind = candidate
    try:
        soup = page(path)
    except requests.RequestException:
        return None
    heading = soup.find("h1")
    artwork = poster(soup)
    if not heading or not artwork:
        return None
    title = heading.get_text(strip=True)
    values = list(soup.stripped_strings)
    try:
        start = values.index(title)
        end = values.index("Reference materials", start) if "Reference materials" in values[start:] else start + 85
        brief = values[start:end]
    except ValueError:
        return None
    if "Accepting clips" not in brief:
        return None
    result = {"title": title[:160], "poster": artwork, "kind": kind, "gaming": bool(GAME.search(title)),
              "organizer": values[start - 1][:85] if start else ""}
    if kind == "pool":
        for index in range(len(brief) - 2):
            if brief[index:index + 2] == ["Pool", "Pool"]:
                amounts = dollars(brief[index + 2])
                if amounts:
                    result.update(amount=amounts[0], shared_by_views="Views" in brief[index + 3:index + 6])
                    return result if amounts[0] >= 5000 else None
        return None

    rates = []
    variable = False
    for index, value in enumerate(brief[:-2]):
        if value == "Per 1K views":
            cap = brief[index + 1] == "Up to"
            amounts = dollars(brief[index + 1 + cap])
            if amounts:
                rates.extend(amounts)
                variable |= cap
    if not rates or max(rates) < 2:
        return None
    result.update(amount=max(rates), minimum=min(rates), variable=variable)
    if "Budget" in brief:
        budget = brief[brief.index("Budget") + 1:]
        if "/" in budget:
            total = budget.index("/") + 1
            if total < len(budget) and dollars(budget[total]):
                result["budget"] = dollars(budget[total])[0]
    return result


def fetch_offers():
    choices = candidates(page("/c/discover"))
    with ThreadPoolExecutor(max_workers=6) as pool:
        verified = [offer for offer in pool.map(details, choices) if offer]
    pools = sorted((row for row in verified if row["kind"] == "pool"),
                   key=lambda row: (row["gaming"], row["amount"]), reverse=True)
    rates = sorted((row for row in verified if row["kind"] == "rate"),
                   key=lambda row: (row["amount"], row.get("budget", 0)), reverse=True)
    return (pools[:1] + rates[:1] + pools[1:] + rates[1:])[:3]


class DealCache:
    def __init__(self):
        self.lock = Lock()
        self.next_check = 0
        self.expires = 0
        self.data = {"deals": [], "checked": None}

    def get(self):
        with self.lock:
            now = monotonic()
            if now < self.next_check:
                return self.data if now < self.expires else {"deals": [], "checked": None}
            self.next_check = now + 60
            try:
                offers = fetch_offers()
            except (requests.RequestException, ValueError) as exc:
                LOG.info("Content Rewards offers unavailable: %s", exc)
                return self.data if now < self.expires else {"deals": [], "checked": None}
            self.next_check = monotonic() + 600
            self.expires = self.next_check + 1200
            self.data = {"deals": offers, "checked": datetime.now(timezone.utc).isoformat()}
            return self.data
