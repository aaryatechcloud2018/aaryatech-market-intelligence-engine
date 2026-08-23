"""
Apple App Store collector.

Uses Apple's public customer-reviews RSS feed (JSON format) -- no
credentials required:
  https://itunes.apple.com/{country}/rss/customerreviews/id={app_id}/page={n}/sortby=mostrecent/json

Collects, per RAW_FIELDS: review title + body (combined into comment_text --
still the original text, just title and body concatenated, never prefixed
with synthetic metadata), star rating (its own `rating` field), date,
reviewer name, and app version (folded into thread_or_page_title).

Note: this feed only exposes roughly the most recent ~500 reviews (10 pages
x ~50), so very old date windows may return nothing -- that limitation is
documented in the Stage 2 collection notes, not hidden.
"""

from __future__ import annotations

from datetime import date, datetime

import requests

from src.audience_collection.collectors.base import empty_raw_row, make_comment_id, now_iso
from src.audience_collection.config import (
    APP_STORE_APP_ID,
    APP_STORE_COUNTRY,
    APP_STORE_MAX_PAGES,
    BRAND,
    CAMPAIGN_OR_EVENT,
    DEFAULT_PRODUCT,
)

PLATFORM = "app_store"
SOURCE_URL = f"https://apps.apple.com/{APP_STORE_COUNTRY}/app/id{APP_STORE_APP_ID}"


def _feed_url(page: int) -> str:
    return (
        f"https://itunes.apple.com/{APP_STORE_COUNTRY}/rss/customerreviews/"
        f"page={page}/id={APP_STORE_APP_ID}/sortby=mostrecent/json"
    )


def collect(window_start: date, window_end: date) -> list[dict]:
    """Collect Apple App Store reviews for APP_STORE_APP_ID within the date window."""
    session = requests.Session()
    rows: list[dict] = []

    for page in range(1, APP_STORE_MAX_PAGES + 1):
        resp = session.get(_feed_url(page), timeout=20)
        if resp.status_code != 200:
            break
        entries = resp.json().get("feed", {}).get("entry", [])
        if not entries:
            break
        # entry[0] is feed metadata (app info), not a review, when present
        entries = [e for e in entries if "im:rating" in e]

        stop = False
        for entry in entries:
            review_date_raw = entry["updated"]["label"]
            review_date = datetime.fromisoformat(review_date_raw.replace("Z", "+00:00")).date()
            if review_date < window_start:
                stop = True
                continue
            if review_date > window_end:
                continue

            app_version = entry.get("im:version", {}).get("label", "unknown version")
            rating = entry.get("im:rating", {}).get("label", "?")
            title = entry.get("title", {}).get("label", "")
            body = entry.get("content", {}).get("label", "")
            review_id = entry.get("id", {}).get("label", "")
            author = entry.get("author", {}).get("name", {}).get("label", "Anonymous")

            row = empty_raw_row()
            row.update(
                {
                    "comment_id": make_comment_id(PLATFORM, review_id),
                    "record_type": "REVIEW",
                    "platform": PLATFORM,
                    "subreddit": "",
                    "post_id": "",
                    "source_url": SOURCE_URL,
                    "thread_or_page_title": f"App Store review (app version: {app_version})",
                    "public_username": author,
                    "comment_text": f"{title}: {body}" if title else body,
                    "rating": rating,
                    "comment_date": review_date.isoformat(),
                    "collected_at": now_iso(),
                    "likes_or_upvotes": "",  # not exposed by this feed
                    "reply_count": "",  # not exposed by this feed
                    "parent_comment_id": "",
                    "brand": BRAND,
                    "product": DEFAULT_PRODUCT,
                    "campaign_or_event": CAMPAIGN_OR_EVENT,
                    "raw_status": "COLLECTED",
                }
            )
            rows.append(row)

        if stop:
            break

    return rows
