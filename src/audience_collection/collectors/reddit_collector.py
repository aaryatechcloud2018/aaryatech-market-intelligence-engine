"""
Reddit collector.

WHY THE OLD METHOD FAILED (403 Client Error: Blocked)
------------------------------------------------------
The previous version of this collector used Reddit's public, unauthenticated
".json" endpoints (e.g. reddit.com/r/Wealthsimple/search.json) -- no login
required. That used to work for years, but Reddit has since locked this
down: it now actively detects and blocks traffic that isn't either (a) a
real logged-in browser session, or (b) an application using Reddit's
official OAuth API. A Python script's plain HTTP request looks like (b) but
isn't authenticated, so Reddit's server now returns "403 Blocked" on sight
-- this is Reddit's own anti-scraping policy, not a bug in our code, and not
something a network/proxy setting can fix. Retrying the same request just
gets the same block (and risks a longer/IP-level block), so this collector
no longer attempts it automatically.

THE FIX: Reddit's official API via OAuth (PRAW)
------------------------------------------------------
This is now the ONLY supported method, matching Reddit's own terms of
service. It requires a free Reddit "script" app -- see
data/audience/README.md or the Stage 2 chat summary for exact setup steps.
If REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET are not set, collect() raises
RedditCredentialsMissingError with the details up front, rather than
attempting (and failing) a live call.

WHAT THIS COLLECTS
------------------------------------------------------
Both POSTS and COMMENTS (kept as separate record_type values, linked via
post_id/parent_comment_id/subreddit/thread title -- see schema.py). Search
runs every query in config.REDDIT_SEARCH_QUERIES across every subreddit in
config.REDDIT_SUBREDDITS, PLUS a sitewide search (r/all) so relevant
discussion outside the named subreddits isn't blindly excluded. Each unique
post is only processed once even if multiple queries/subreddits surface it.
Every post's own date AND every individual comment's own date are checked
against the window independently -- a post started before the window can
still contribute comments that fall inside it, and vice versa.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from src.audience_collection.collectors.base import empty_raw_row, make_comment_id, now_iso
from src.audience_collection.config import (
    BRAND,
    CAMPAIGN_OR_EVENT,
    DEFAULT_PRODUCT,
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_SEARCH_QUERIES,
    REDDIT_SITEWIDE_SUBREDDIT,
    REDDIT_SUBREDDITS,
    REDDIT_USER_AGENT,
)

PLATFORM = "reddit"


class RedditCredentialsMissingError(RuntimeError):
    """Raised when REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET are not configured.
    Reddit's public unauthenticated endpoints are confirmed blocked (403),
    so there is no working fallback -- OAuth credentials are required."""

    def __init__(self) -> None:
        super().__init__(
            "Reddit collection requires OAuth credentials (REDDIT_CLIENT_ID and "
            "REDDIT_CLIENT_SECRET) -- Reddit's unauthenticated public endpoints now "
            "return 403 Blocked. Get a free 'script' app at "
            "https://www.reddit.com/prefs/apps, then add REDDIT_CLIENT_ID and "
            "REDDIT_CLIENT_SECRET to your local .env file. See "
            "data/audience/README.md for the exact steps."
        )


def _in_window(created_utc: float, window_start: date, window_end: date) -> bool:
    d = datetime.fromtimestamp(created_utc, tz=timezone.utc).date()
    return window_start <= d <= window_end


def _row_from_submission(sub: dict, subreddit: str, source_url: str) -> dict:
    """Pure row-shaping logic for a POST -- kept separate from any PRAW call
    so it can be unit tested with a plain dict, no network needed."""
    row = empty_raw_row()
    row.update(
        {
            "comment_id": make_comment_id(PLATFORM, f"post_{sub['id']}"),
            "record_type": "POST",
            "platform": PLATFORM,
            "subreddit": subreddit,
            "post_id": sub["id"],
            "source_url": source_url,
            "thread_or_page_title": sub.get("title", ""),
            "public_username": sub.get("author") or "[deleted]",
            "comment_text": sub.get("selftext") or sub.get("title", ""),  # original text, untouched
            "rating": "",
            "comment_date": datetime.fromtimestamp(sub["created_utc"], tz=timezone.utc).isoformat(),
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


def _row_from_comment(comment: dict, subreddit: str, post_id: str, thread_title: str, thread_url: str) -> dict:
    """Pure row-shaping logic for a COMMENT. parent_comment_id resolves to:
    - the post's own universal comment_id, if this is a top-level comment
      (Reddit's parent_id starts with t3_, the post's native ID), or
    - the parent comment's universal comment_id, if this is a nested reply
      (Reddit's parent_id starts with t1_).
    """
    row = empty_raw_row()
    parent_id = comment.get("parent_id", "")
    if parent_id.startswith("t1_"):
        parent_comment_id = make_comment_id(PLATFORM, parent_id.split("_", 1)[1])
    elif parent_id.startswith("t3_"):
        parent_comment_id = make_comment_id(PLATFORM, f"post_{parent_id.split('_', 1)[1]}")
    else:
        parent_comment_id = ""

    row.update(
        {
            "comment_id": make_comment_id(PLATFORM, comment["id"]),
            "record_type": "COMMENT",
            "platform": PLATFORM,
            "subreddit": subreddit,
            "post_id": post_id,
            "source_url": f"{thread_url.rstrip('/')}/{comment['id']}/",
            "thread_or_page_title": thread_title,
            "public_username": comment.get("author") or "[deleted]",
            "comment_text": comment.get("body", ""),  # original text, untouched
            "rating": "",
            "comment_date": datetime.fromtimestamp(comment["created_utc"], tz=timezone.utc).isoformat(),
            "collected_at": now_iso(),
            "likes_or_upvotes": comment.get("score", ""),
            "reply_count": comment.get("reply_count", 0),
            "parent_comment_id": parent_comment_id,
            "brand": BRAND,
            "product": DEFAULT_PRODUCT,
            "campaign_or_event": CAMPAIGN_OR_EVENT,
            "raw_status": "COLLECTED",
        }
    )
    return row


def _collect_via_praw(window_start: date, window_end: date) -> list[dict]:
    import praw  # imported lazily -- only needed on this path

    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
    )

    # Discover candidate submissions across every configured subreddit AND a
    # sitewide search, deduplicated by Reddit's own post ID so a post found
    # by multiple queries/subreddits is only processed once.
    candidates: dict[str, tuple[object, str]] = {}  # post_id -> (submission, subreddit_it_was_found_in)
    search_targets = REDDIT_SUBREDDITS + [REDDIT_SITEWIDE_SUBREDDIT]
    for subreddit_name in search_targets:
        subreddit = reddit.subreddit(subreddit_name)
        for query in REDDIT_SEARCH_QUERIES:
            for submission in subreddit.search(query, sort="new", time_filter="year", limit=100):
                if submission.id not in candidates:
                    # record the subreddit it actually lives in, not the one we searched from
                    candidates[submission.id] = (submission, str(submission.subreddit))

    rows: list[dict] = []
    for submission, subreddit_name in candidates.values():
        permalink = f"https://www.reddit.com{submission.permalink}"

        if _in_window(submission.created_utc, window_start, window_end):
            rows.append(
                _row_from_submission(
                    {
                        "id": submission.id,
                        "title": submission.title,
                        "selftext": submission.selftext,
                        "author": str(submission.author) if submission.author else None,
                        "created_utc": submission.created_utc,
                        "score": submission.score,
                        "num_comments": submission.num_comments,
                    },
                    subreddit_name,
                    permalink,
                )
            )

        # Comments are evaluated independently of the post's own date -- an
        # older thread can still receive in-window comments.
        submission.comments.replace_more(limit=0)
        for comment in submission.comments.list():
            if not _in_window(comment.created_utc, window_start, window_end):
                continue
            rows.append(
                _row_from_comment(
                    {
                        "id": comment.id,
                        "body": comment.body,
                        "author": str(comment.author) if comment.author else None,
                        "created_utc": comment.created_utc,
                        "score": comment.score,
                        "parent_id": comment.parent_id,
                        "reply_count": len(comment.replies) if hasattr(comment, "replies") else 0,
                    },
                    subreddit_name,
                    submission.id,
                    submission.title,
                    permalink,
                )
            )

    return rows


def collect(window_start: date, window_end: date) -> list[dict]:
    """Collect Reddit posts + comments about Wealthsimple within the given
    date window. Requires REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET -- raises
    RedditCredentialsMissingError immediately if they're not set, rather
    than attempting the now-blocked unauthenticated endpoints."""
    if not (REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET):
        raise RedditCredentialsMissingError()
    return _collect_via_praw(window_start, window_end)
