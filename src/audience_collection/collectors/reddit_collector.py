"""
Reddit collector.

Primary method: Reddit's public, unauthenticated .json endpoints (no
credentials required). This is the "closest practical alternative" if full
OAuth access isn't set up, but Reddit has increasingly rate-limited or
blocked unauthenticated traffic -- if that happens (403/429), set
REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET (a free Reddit "script" app) as
environment variables and this collector automatically switches to PRAW
(OAuth) instead.

Collects, per src/audience_collection/schema.py RAW_FIELDS: post title,
post URL, comment text, username, date, score/upvotes, and parent/thread
context (parent_comment_id + thread_or_page_title).
"""

from __future__ import annotations

import time
from datetime import date, datetime, timezone

import requests

from src.audience_collection.collectors.base import empty_raw_row, make_comment_id, now_iso
from src.audience_collection.config import (
    BRAND,
    CAMPAIGN_OR_EVENT,
    DEFAULT_PRODUCT,
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_SEARCH_QUERY,
    REDDIT_SUBREDDITS,
    REDDIT_USER_AGENT,
)

PLATFORM = "reddit"


def _in_window(created_utc: float, window_start: date, window_end: date) -> bool:
    d = datetime.fromtimestamp(created_utc, tz=timezone.utc).date()
    return window_start <= d <= window_end


def _row_from_submission(sub: dict, source_url: str) -> dict:
    row = empty_raw_row()
    row.update(
        {
            "comment_id": make_comment_id(PLATFORM, f"post_{sub['id']}"),
            "platform": PLATFORM,
            "source_url": source_url,
            "thread_or_page_title": sub.get("title", ""),
            "public_username": sub.get("author", "[deleted]"),
            "comment_text": sub.get("selftext") or sub.get("title", ""),
            "comment_date": datetime.fromtimestamp(
                sub["created_utc"], tz=timezone.utc
            ).isoformat(),
            "collected_at": now_iso(),
            "likes_or_upvotes": sub.get("score", ""),
            "reply_count": sub.get("num_comments", ""),
            "parent_comment_id": "",
            "brand": BRAND,
            "product": DEFAULT_PRODUCT,
            "campaign_or_event": CAMPAIGN_OR_EVENT,
            "raw_status": "COLLECTED",
        }
    )
    return row


def _row_from_comment(comment: dict, thread_title: str, thread_url: str) -> dict:
    row = empty_raw_row()
    parent_id = comment.get("parent_id", "")
    parent_comment_id = (
        make_comment_id(PLATFORM, parent_id.split("_", 1)[1])
        if parent_id.startswith("t1_")
        else ""
    )
    row.update(
        {
            "comment_id": make_comment_id(PLATFORM, comment["id"]),
            "platform": PLATFORM,
            "source_url": f"{thread_url.rstrip('/')}/{comment['id']}/",
            "thread_or_page_title": thread_title,
            "public_username": comment.get("author", "[deleted]"),
            "comment_text": comment.get("body", ""),
            "comment_date": datetime.fromtimestamp(
                comment["created_utc"], tz=timezone.utc
            ).isoformat(),
            "collected_at": now_iso(),
            "likes_or_upvotes": comment.get("score", ""),
            "reply_count": len(comment.get("replies", {}).get("data", {}).get("children", []))
            if isinstance(comment.get("replies"), dict)
            else 0,
            "parent_comment_id": parent_comment_id,
            "brand": BRAND,
            "product": DEFAULT_PRODUCT,
            "campaign_or_event": CAMPAIGN_OR_EVENT,
            "raw_status": "COLLECTED",
        }
    )
    return row


def _collect_via_public_json(window_start: date, window_end: date) -> list[dict]:
    session = requests.Session()
    session.headers.update({"User-Agent": REDDIT_USER_AGENT})
    rows: list[dict] = []

    for subreddit in REDDIT_SUBREDDITS:
        search_url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = {
            "q": REDDIT_SEARCH_QUERY,
            "restrict_sr": "1",
            "sort": "new",
            "limit": 100,
        }
        resp = session.get(search_url, params=params, timeout=20)
        resp.raise_for_status()
        posts = resp.json()["data"]["children"]

        for post in posts:
            sub = post["data"]
            if not _in_window(sub["created_utc"], window_start, window_end):
                continue
            permalink = f"https://www.reddit.com{sub['permalink']}"
            rows.append(_row_from_submission(sub, permalink))

            comments_url = f"{permalink.rstrip('/')}.json"
            time.sleep(1)  # be polite -- unauthenticated endpoint, easy to get rate-limited
            c_resp = session.get(comments_url, params={"limit": 200}, timeout=20)
            if c_resp.status_code != 200:
                continue
            listings = c_resp.json()
            if len(listings) < 2:
                continue
            for child in listings[1]["data"]["children"]:
                if child["kind"] != "t1":
                    continue
                comment = child["data"]
                if not _in_window(comment["created_utc"], window_start, window_end):
                    continue
                rows.append(_row_from_comment(comment, sub.get("title", ""), permalink))
            time.sleep(1)

    return rows


def _collect_via_praw(window_start: date, window_end: date) -> list[dict]:
    import praw  # imported lazily -- only needed on this path

    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
    )
    rows: list[dict] = []
    for subreddit_name in REDDIT_SUBREDDITS:
        subreddit = reddit.subreddit(subreddit_name)
        for submission in subreddit.search(REDDIT_SEARCH_QUERY, sort="new", limit=100):
            if not _in_window(submission.created_utc, window_start, window_end):
                continue
            permalink = f"https://www.reddit.com{submission.permalink}"
            rows.append(
                _row_from_submission(
                    {
                        "id": submission.id,
                        "title": submission.title,
                        "selftext": submission.selftext,
                        "author": str(submission.author) if submission.author else "[deleted]",
                        "created_utc": submission.created_utc,
                        "score": submission.score,
                        "num_comments": submission.num_comments,
                    },
                    permalink,
                )
            )
            submission.comments.replace_more(limit=0)
            for comment in submission.comments.list():
                if not _in_window(comment.created_utc, window_start, window_end):
                    continue
                rows.append(
                    _row_from_comment(
                        {
                            "id": comment.id,
                            "body": comment.body,
                            "author": str(comment.author) if comment.author else "[deleted]",
                            "created_utc": comment.created_utc,
                            "score": comment.score,
                            "parent_id": comment.parent_id,
                            "replies": {},
                        },
                        submission.title,
                        permalink,
                    )
                )
    return rows


def collect(window_start: date, window_end: date) -> list[dict]:
    """Collect Reddit posts + comments mentioning REDDIT_SEARCH_QUERY within
    the given date window, from the configured subreddits.

    Uses PRAW/OAuth if REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET are set;
    otherwise falls back to the unauthenticated public .json endpoints.
    """
    if REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET:
        return _collect_via_praw(window_start, window_end)
    return _collect_via_public_json(window_start, window_end)
