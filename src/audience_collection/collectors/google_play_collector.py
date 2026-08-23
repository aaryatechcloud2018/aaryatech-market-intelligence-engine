"""
Google Play collector.

Uses the `google-play-scraper` package, which reads Google Play's public
review data (the same data shown on the store listing page) -- no
credentials required.

Collects, per RAW_FIELDS: review text, rating (mapped into likes_or_upvotes'
sibling comment_text via cleaned text -- rating itself has no dedicated raw
field in the shared schema, so it is appended to comment_text as
"[Rating: X/5] <text>" to keep it human-readable without breaking the
common schema), date, reviewer name, helpful ("thumbsUpCount") count, and
app version (folded into thread_or_page_title since the shared schema has
no per-platform-only column).
"""

from __future__ import annotations

from datetime import date

from google_play_scraper import Sort, reviews

from src.audience_collection.collectors.base import empty_raw_row, make_comment_id, now_iso
from src.audience_collection.config import (
    BRAND,
    CAMPAIGN_OR_EVENT,
    DEFAULT_PRODUCT,
    GOOGLE_PLAY_APP_ID,
    GOOGLE_PLAY_COUNTRY,
    GOOGLE_PLAY_LANG,
)

PLATFORM = "google_play"
SOURCE_URL = f"https://play.google.com/store/apps/details?id={GOOGLE_PLAY_APP_ID}"


def collect(window_start: date, window_end: date, max_count: int = 2000) -> list[dict]:
    """Collect Google Play reviews for GOOGLE_PLAY_APP_ID within the date window."""
    rows: list[dict] = []
    continuation_token = None
    fetched = 0

    while fetched < max_count:
        batch, continuation_token = reviews(
            GOOGLE_PLAY_APP_ID,
            lang=GOOGLE_PLAY_LANG,
            country=GOOGLE_PLAY_COUNTRY,
            sort=Sort.NEWEST,
            count=200,
            continuation_token=continuation_token,
        )
        if not batch:
            break
        fetched += len(batch)

        stop = False
        for r in batch:
            review_date = r["at"].date()
            if review_date < window_start:
                stop = True
                continue
            if review_date > window_end:
                continue

            app_version = r.get("reviewCreatedVersion") or r.get("appVersion") or "unknown version"
            row = empty_raw_row()
            row.update(
                {
                    "comment_id": make_comment_id(PLATFORM, r["reviewId"]),
                    "platform": PLATFORM,
                    "source_url": SOURCE_URL,
                    "thread_or_page_title": f"Google Play review (app version: {app_version})",
                    "public_username": r.get("userName", "Anonymous"),
                    "comment_text": f"[Rating: {r.get('score', '?')}/5] {r.get('content', '')}",
                    "comment_date": review_date.isoformat(),
                    "collected_at": now_iso(),
                    "likes_or_upvotes": r.get("thumbsUpCount", 0),
                    "reply_count": 1 if r.get("replyContent") else 0,
                    "parent_comment_id": "",
                    "brand": BRAND,
                    "product": DEFAULT_PRODUCT,
                    "campaign_or_event": CAMPAIGN_OR_EVENT,
                    "raw_status": "COLLECTED",
                }
            )
            rows.append(row)

        if stop or not continuation_token:
            break

    return rows
