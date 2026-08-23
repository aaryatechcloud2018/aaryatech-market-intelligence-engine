"""
Google Play collector.

Uses the `google-play-scraper` package, which reads Google Play's public
review data (the same data shown on the store listing page) -- no
credentials required. Confirmed working against real data on a machine
with normal internet access (this sandbox environment's own network egress
is blocked at the policy level -- see data/audience/README.md).

Collects, per RAW_FIELDS: original review text (verbatim, never prefixed or
otherwise mutated), star rating (its own `rating` field), date, reviewer
name, helpful ("thumbsUpCount") count, and app version (folded into
thread_or_page_title, since the shared schema has no per-platform-only
column for it).

Paging stops only once review dates page past window_start (Google Play
returns reviews newest-first) or the API runs out of pages -- never an
artificial row-count cutoff within that. GOOGLE_PLAY_MAX_FETCH is a safety
valve far above any realistic single-app review volume, not a real limit.
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
    GOOGLE_PLAY_MAX_FETCH,
)

PLATFORM = "google_play"
SOURCE_URL = f"https://play.google.com/store/apps/details?id={GOOGLE_PLAY_APP_ID}"


class GooglePlayFetchError(RuntimeError):
    """Raised when the underlying API returned literally zero reviews across
    every page fetched -- not just zero within the date window. Real apps
    with Wealthsimple's install base have far more than a handful of total
    reviews, so a totally empty first fetch is a strong signal of a network/
    connectivity problem, not a legitimate "no reviews" result. This matters
    because `google_play_scraper` itself swallows connection failures
    silently and just returns an empty list -- without this check, a
    blocked network would misleadingly look identical to "0 valid rows"."""

    def __init__(self) -> None:
        super().__init__(
            "Google Play returned zero reviews across every page fetched, which is "
            "implausible for an app with Wealthsimple's install base. This almost "
            "certainly means the request never actually reached Google Play (e.g. "
            "no internet access from this environment), not that there are no "
            "reviews. Check network connectivity before trusting a 0-row result."
        )


def _row_from_review(r: dict) -> dict:
    """Pure, network-independent row-shaping logic -- kept separate from
    collect() so it can be unit tested with a fake review dict."""
    review_date = r["at"].date() if hasattr(r["at"], "date") else r["at"]
    app_version = r.get("reviewCreatedVersion") or r.get("appVersion") or "unknown version"
    row = empty_raw_row()
    row.update(
        {
            "comment_id": make_comment_id(PLATFORM, r["reviewId"]),
            "record_type": "REVIEW",
            "platform": PLATFORM,
            "subreddit": "",
            "post_id": "",
            "source_url": SOURCE_URL,
            "thread_or_page_title": f"Google Play review (app version: {app_version})",
            "public_username": r.get("userName", "Anonymous"),
            "comment_text": r.get("content", ""),  # original text, untouched
            "rating": r.get("score", ""),
            "comment_date": review_date.isoformat() if hasattr(review_date, "isoformat") else str(review_date),
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
    return row


def collect(window_start: date, window_end: date, max_count: int = GOOGLE_PLAY_MAX_FETCH) -> list[dict]:
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
            rows.append(_row_from_review(r))

        if stop or not continuation_token:
            break

    if fetched == 0:
        raise GooglePlayFetchError()

    return rows
