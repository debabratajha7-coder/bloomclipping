"""Public YouTube uploads and current broadcasts from a curated gaming watchlist."""

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, Thread
from urllib.parse import quote

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from creators import read_store

CHANNELS = (
    "TechnoGamerzOfficial", "TotalGaming093", "GamerFleet", "CarryIsLive",
    "LiveInsaan", "Mythpat", "BeastBoyShub", "DynamoGaming", "officialscoutop",
    "JonathanGamingYT", "PayalGaming", "MortaLyt", "IShowSpeed", "TypicalGamer",
)
REFRESH_SECONDS = 300
LIVE_MAX_AGE = 420
DAY = 86400
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
YOUTUBE_CHANNEL = re.compile(r"@[-\w.]{2,60}|channel/UC[\w-]{20,24}|(?:c|user)/[-\w.]{2,60}")
LOG = logging.getLogger(__name__)


class FeedLogger:
    def debug(self, message):
        pass

    def warning(self, message):
        pass

    def error(self, message):
        LOG.debug("YouTube feed: %s", message)


def public_entries(channel, tab):
    options = {
        "extract_flat": "in_playlist", "playlistend": 4, "skip_download": True,
        "socket_timeout": 8, "retries": 0, "extractor_retries": 0, "quiet": True,
        "extractor_args": {"youtubetab": {"approximate_date": ["true"]}},
        "logger": FeedLogger(),
    }
    with YoutubeDL(options) as youtube:
        try:
            listing = youtube.extract_info(f"https://www.youtube.com/{quote(channel, safe='/@')}/{tab}", download=False)
        except DownloadError as exc:
            if f"This channel does not have a {tab} tab" in str(exc):
                return []
            raise
    return normalize_entries(listing or {}, channel, tab)


def normalize_entries(listing, channel, tab):
    entries = []
    for row in listing.get("entries") or []:
        if not row or not VIDEO_ID.fullmatch(str(row.get("id", ""))) or not row.get("title"):
            continue
        if "/shorts/" in (row.get("url") or ""):
            continue
        status = row.get("live_status")
        if status == "is_upcoming" or (tab == "streams" and status not in ("is_live", "was_live", "post_live")):
            continue
        is_live = status == "is_live"
        entries.append({
            "id": row["id"], "title": row["title"], "live": is_live,
            "creator": row.get("channel") or listing.get("channel") or channel,
            "channel": channel, "published": row.get("timestamp"),
            "channel_id": row.get("channel_id") or listing.get("channel_id"),
            "views": row.get("concurrent_view_count" if is_live else "view_count"),
            "replay": status in ("was_live", "post_live"),
        })
    return entries


def ranked_feed(snapshot, now, include_older=False):
    live, videos = {}, {}
    for result in snapshot.values():
        for row in result["entries"]:
            if row["live"]:
                if now - result["checked"] <= LIVE_MAX_AGE:
                    live[row["id"]] = row
            elif row["id"] not in videos or row["replay"]:
                videos[row["id"]] = row
    # A replay from the streams tab can supersede a lingering live badge on an uploads tab.
    live = {key: row for key, row in live.items()
            if key not in videos or not videos[key]["replay"]}
    candidates = [row for row in videos.values() if row["id"] not in live
                  and (include_older or row["published"] is None or now - row["published"] <= 30 * DAY)]
    latest = sorted(candidates, key=lambda row: row["published"] or 0, reverse=True)

    def popularity(row):
        age = max(.5, (now - row["published"]) / DAY) if row["published"] else 30
        return (row["views"] or 0) / age

    hot = sorted(candidates, key=popularity, reverse=True)
    return {
        "live": sorted(live.values(), key=lambda row: row["views"] or 0, reverse=True),
        "latest": latest[:20],
        "popular": hot[:20],
    }


def youtube_watchlist(rows):
    saved = {}
    for row in rows:
        ref = row.get("ref") if isinstance(row, dict) else None
        if isinstance(ref, str) and row.get("platform") == "youtube" and YOUTUBE_CHANNEL.fullmatch(ref):
            saved[ref.lower()] = ref
    channels = {"@" + handle.lower(): "@" + handle for handle in CHANNELS}
    channels.update(saved)
    return channels, saved


def attach(app, data_dir):
    path = data_dir / "youtube-feed.store"
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(snapshot, dict):
            snapshot = {}
        snapshot = {
            key: item for key, item in snapshot.items()
            if isinstance(item, dict) and isinstance(item.get("checked"), (int, float))
            and isinstance(item.get("entries"), list)
            and all(isinstance(row, dict) and "channel" in row for row in item["entries"])
        }
    except (OSError, ValueError):
        snapshot = {}
    lock = Lock()
    refreshing = False
    attempted = {}
    failed_keys = set()

    def fetch_one(job):
        key, channel, tab = job
        try:
            return key, public_entries(channel, tab)
        except Exception as exc:
            LOG.debug("YouTube feed could not read %s/%s: %s", channel, tab, exc)
            return key, None

    def refresh(jobs):
        nonlocal refreshing
        try:
            with ThreadPoolExecutor(max_workers=6, thread_name_prefix="youtube-feed") as pool:
                for key, rows in pool.map(fetch_one, jobs):
                    with lock:
                        if rows is None:
                            failed_keys.add(key)
                        else:
                            failed_keys.discard(key)
                            snapshot[key] = {"checked": time.time(), "entries": rows}
            with lock:
                pending = path.with_suffix(".tmp")
                pending.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
                pending.replace(path)
        except OSError as exc:
            LOG.warning("Could not save the YouTube feed: %s", exc)
        finally:
            with lock:
                refreshing = False

    @app.get("/youtube-feed")
    def youtube_feed():
        nonlocal refreshing
        now = time.time()
        channels, saved = youtube_watchlist(read_store(data_dir))
        jobs = [(f"{ref}/{tab}", channel, tab) for ref, channel in channels.items()
                for tab in ("streams", "videos")]
        eligible = {key for key, _, _ in jobs}
        saved_keys = {f"{ref}/{tab}" for ref in saved for tab in ("streams", "videos")}
        with lock:
            if not refreshing:
                for key in snapshot.keys() - eligible:
                    del snapshot[key]
                for key in attempted.keys() - eligible:
                    del attempted[key]
                failed_keys.intersection_update(eligible)
            due = [job for job in jobs
                   if now - max(attempted.get(job[0], 0), snapshot.get(job[0], {}).get("checked", 0)) >= REFRESH_SECONDS]
            if not refreshing and due:
                attempted.update((key, now) for key, _, _ in due)
                refreshing = True
                Thread(target=refresh, args=(due,), daemon=True, name="youtube-feed-refresh").start()
            active_snapshot = {key: item for key, item in snapshot.items() if key in eligible}
            saved_snapshot = {key: item for key, item in active_snapshot.items() if key in saved_keys}
            saved_ids = {row["channel_id"] for item in saved_snapshot.values() for row in item["entries"]
                         if row.get("channel_id")}
            latest_live_checks = sum(
                key.endswith("/streams") and now - item["checked"] <= LIVE_MAX_AGE
                for key, item in active_snapshot.items()
            )
            return {
                **ranked_feed(active_snapshot, now),
                "saved_feed": ranked_feed(saved_snapshot, now, include_older=True),
                "saved_channels": list(saved),
                "saved_ids": sorted(saved_ids),
                "updated": max((item["checked"] for item in active_snapshot.values()), default=0),
                "refreshing": refreshing or bool(due), "channels": len(channels),
                "live_checked": latest_live_checks, "failures": len(eligible & failed_keys),
            }
