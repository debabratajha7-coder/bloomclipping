"""Published campaign directory and local-only click totals."""

import json
import logging
import re
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit

from fastapi import HTTPException
from pydantic import BaseModel, Field

from campaign_deals import DealCache

CATALOG = Path(__file__).with_name("campaigns.json")
TEXT_FIELDS = {"name": 64, "pays": 140, "payout": 100, "min_payout": 60, "note": 220, "action": 32}
LOCK = Lock()
LOG = logging.getLogger(__name__)


def https_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return ""
    if not value.startswith("https://") or any(c.isspace() or c == "\\" for c in value):
        return ""
    try:
        url = urlsplit(value)
        if url.hostname and url.username is None and url.password is None:
            return value
    except ValueError:
        pass
    return ""


def read_catalog(path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    platforms = []
    seen = set()
    for row in raw["platforms"]:
        if not isinstance(row, dict):
            continue
        slug, name = row.get("id"), row.get("name")
        url = https_url(row.get("referral_url"))
        if not url or not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9-]{1,32}", slug):
            continue
        if slug in seen or not isinstance(name, str) or not name.strip():
            continue
        fields = {key: row[key].strip()[:limit] for key, limit in TEXT_FIELDS.items()
                  if isinstance(row.get(key), str)}
        tags = row.get("good_for", [])
        platforms.append({
            **fields, "id": slug, "referral_url": url,
            "india": row.get("india") == "Yes",
            "good_for": [tag for tag in tags if tag in ("GTA", "Streams", "Podcasts", "UGC", "Music")]
            if isinstance(tags, list) else [],
        })
        seen.add(slug)
    return {"updated": str(raw.get("updated", ""))[:10], "platforms": platforms}


def read_counts(path):
    try:
        counts = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(counts, dict):
        return {}
    return {key: count for key, count in counts.items() if type(count) is int and count >= 0}


class CampaignOpen(BaseModel):
    id: str = Field(max_length=32)


def attach(app, data_dir):
    clicks = data_dir / "campaign-clicks.json"
    deals = DealCache()

    def catalog():
        try:
            return read_catalog(CATALOG)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            LOG.warning("Campaign directory unavailable: %s", exc)
            raise HTTPException(503, "Campaigns are temporarily unavailable.") from exc

    @app.get("/campaigns")
    def list_campaigns():
        result = catalog()
        counts = read_counts(clicks)
        result["platforms"].sort(key=lambda row: -counts.get(row["id"], 0))
        return result

    @app.post("/campaigns/open")
    def open_campaign(selection: CampaignOpen):
        row = next((row for row in catalog()["platforms"] if row["id"] == selection.id), None)
        if row is None:
            raise HTTPException(404, "Campaign platform not found.")
        with LOCK:
            counts = read_counts(clicks)
            counts[row["id"]] = counts.get(row["id"], 0) + 1
            try:
                pending = clicks.with_suffix(".tmp")
                pending.write_text(json.dumps(counts), encoding="utf-8")
                pending.replace(clicks)
            except OSError as exc:
                LOG.warning("Could not save campaign click totals: %s", exc)
        return {"url": row["referral_url"]}

    @app.get("/campaigns/deals")
    def list_deals():
        if not any(row["id"] == "contentrewards" for row in catalog()["platforms"]):
            return {"deals": [], "checked": None}
        return deals.get()
