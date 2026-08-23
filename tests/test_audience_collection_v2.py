"""
Tests for the Feb-Jul 2026 Google Play + Reddit collection update:
- Google Play row-shaping keeps original text pure (no rating prefix)
- Reddit post/comment linkage (post_id, parent_comment_id, subreddit)
- Reddit date-window filtering
- Windowed, per-platform-folder raw/cleaned file paths
- The three new manual-review CSVs (column layout, blank behavioral columns)
- Missing Reddit credentials raise a clear error instead of a network call

Uses small synthetic fixture rows only (clearly marked [TEST FIXTURE]) --
no live network collection is exercised here.
"""

from datetime import date, datetime, timezone

import pytest

from src.audience_collection import config
from src.audience_collection.cleaning.quality_flags import apply_quality_flags
from src.audience_collection.collectors.google_play_collector import GooglePlayFetchError, _row_from_review, collect as google_play_collect
from src.audience_collection.collectors.reddit_collector import (
    RedditCredentialsMissingError,
    _in_window,
    _row_from_comment,
    _row_from_submission,
    collect as reddit_collect,
)
from src.audience_collection.human_review import build_manual_review_csv
from src.audience_collection.schema import MANUAL_REVIEW_FRONT_FIELDS, MANUAL_REVIEW_V2_FIELDS


# --- Google Play: original text must stay pure, rating is its own field ----

def test_google_play_row_keeps_original_text_pure_and_rating_separate():
    fake_review = {
        "reviewId": "abc123",
        "userName": "TestReviewer",
        "content": "[TEST FIXTURE] The chequing account has been great this year.",
        "score": 5,
        "at": datetime(2026, 3, 15),
        "thumbsUpCount": 2,
        "reviewCreatedVersion": "3.1.0",
    }
    row = _row_from_review(fake_review)
    assert row["comment_text"] == "[TEST FIXTURE] The chequing account has been great this year."
    assert row["rating"] == 5
    assert row["record_type"] == "REVIEW"
    assert row["comment_date"] == "2026-03-15"
    assert "[Rating" not in row["comment_text"]  # the old v1 bug must not reappear


def test_google_play_raises_clear_error_on_totally_empty_fetch(monkeypatch):
    """A network failure inside google_play_scraper is swallowed internally
    and returns an empty list rather than raising -- collect() must turn
    that into a loud, honest error instead of a misleading '0 rows' result."""
    def fake_reviews(*args, **kwargs):
        return [], None

    monkeypatch.setattr("src.audience_collection.collectors.google_play_collector.reviews", fake_reviews)
    with pytest.raises(GooglePlayFetchError, match="implausible"):
        google_play_collect(date(2026, 2, 1), date(2026, 7, 31))


# --- Reddit: post <-> comment linkage ---------------------------------------

def test_reddit_post_and_comment_share_post_id_and_subreddit():
    post = _row_from_submission(
        {
            "id": "postid1",
            "title": "[TEST FIXTURE] Anyone else move their TFSA to Wealthsimple?",
            "selftext": "[TEST FIXTURE] Just did it, curious what others think.",
            "author": "op_user",
            "created_utc": datetime(2026, 3, 1, tzinfo=timezone.utc).timestamp(),
            "score": 10,
            "num_comments": 2,
        },
        "Wealthsimple",
        "https://www.reddit.com/r/Wealthsimple/comments/postid1/",
    )
    top_level_comment = _row_from_comment(
        {
            "id": "c1",
            "body": "[TEST FIXTURE] I did the same thing last month.",
            "author": "commenter_a",
            "created_utc": datetime(2026, 3, 2, tzinfo=timezone.utc).timestamp(),
            "score": 4,
            "parent_id": "t3_postid1",  # t3_ = reply to the POST itself
            "reply_count": 1,
        },
        "Wealthsimple",
        "postid1",
        post["thread_or_page_title"],
        "https://www.reddit.com/r/Wealthsimple/comments/postid1/",
    )
    nested_reply = _row_from_comment(
        {
            "id": "c2",
            "body": "[TEST FIXTURE] How long did the transfer take for you?",
            "author": "commenter_b",
            "created_utc": datetime(2026, 3, 3, tzinfo=timezone.utc).timestamp(),
            "score": 1,
            "parent_id": "t1_c1",  # t1_ = reply to another COMMENT
            "reply_count": 0,
        },
        "Wealthsimple",
        "postid1",
        post["thread_or_page_title"],
        "https://www.reddit.com/r/Wealthsimple/comments/postid1/",
    )

    assert post["record_type"] == "POST"
    assert top_level_comment["record_type"] == "COMMENT"
    assert nested_reply["record_type"] == "COMMENT"

    # all three share the same post_id and subreddit
    assert top_level_comment["post_id"] == post["post_id"] == "postid1"
    assert nested_reply["post_id"] == "postid1"
    assert post["subreddit"] == top_level_comment["subreddit"] == nested_reply["subreddit"] == "Wealthsimple"

    # top-level comment's parent is the POST's own universal comment_id
    assert top_level_comment["parent_comment_id"] == post["comment_id"]
    # nested reply's parent is the COMMENT's universal comment_id
    assert nested_reply["parent_comment_id"] == top_level_comment["comment_id"]


def test_reddit_deleted_author_handled_without_crashing():
    row = _row_from_submission(
        {"id": "p2", "title": "[TEST FIXTURE] t", "selftext": "", "author": None,
         "created_utc": datetime(2026, 3, 1, tzinfo=timezone.utc).timestamp(), "score": 0, "num_comments": 0},
        "Wealthsimple", "https://www.reddit.com/r/Wealthsimple/comments/p2/",
    )
    assert row["public_username"] == "[deleted]"


# --- Reddit: strict date window ---------------------------------------------

def test_reddit_in_window_boundaries():
    window_start = date(2026, 2, 1)
    window_end = date(2026, 7, 31)
    just_inside_start = datetime(2026, 2, 1, 0, 0, 1, tzinfo=timezone.utc).timestamp()
    just_inside_end = datetime(2026, 7, 31, 23, 59, 0, tzinfo=timezone.utc).timestamp()
    before = datetime(2026, 1, 31, 23, 59, tzinfo=timezone.utc).timestamp()
    after = datetime(2026, 8, 1, 0, 0, 1, tzinfo=timezone.utc).timestamp()

    assert _in_window(just_inside_start, window_start, window_end) is True
    assert _in_window(just_inside_end, window_start, window_end) is True
    assert _in_window(before, window_start, window_end) is False
    assert _in_window(after, window_start, window_end) is False


def test_reddit_collect_raises_clear_error_without_credentials(monkeypatch):
    monkeypatch.setattr("src.audience_collection.collectors.reddit_collector.REDDIT_CLIENT_ID", None)
    monkeypatch.setattr("src.audience_collection.collectors.reddit_collector.REDDIT_CLIENT_SECRET", None)
    with pytest.raises(RedditCredentialsMissingError, match="REDDIT_CLIENT_ID"):
        reddit_collect(date(2026, 2, 1), date(2026, 7, 31))


# --- Windowed, per-platform-folder paths ------------------------------------

def test_windowed_paths_use_platform_subfolder_and_date_stamp():
    start, end = date(2026, 2, 1), date(2026, 7, 31)
    raw_path = config.raw_path_for("google_play", start, end)
    cleaned_path = config.cleaned_path_for("reddit", start, end)
    assert raw_path.parent.name == "google_play"
    assert raw_path.name == "wealthsimple_google_play_2026-02-01_to_2026-07-31_raw.csv"
    assert cleaned_path.parent.name == "reddit"
    assert cleaned_path.name == "wealthsimple_reddit_2026-02-01_to_2026-07-31_cleaned.csv"


# --- Manual-review CSVs (v2): readable column layout, blank behavioral cols -

def _cleaned_fixture_row(platform, rating="", subreddit="", record_type="REVIEW"):
    row = {
        "comment_id": f"{platform}_1",
        "record_type": record_type,
        "platform": platform,
        "subreddit": subreddit,
        "post_id": "",
        "source_url": "https://example.invalid/1",
        "thread_or_page_title": "[TEST FIXTURE] title",
        "public_username": "test_user",
        "comment_text": "[TEST FIXTURE] a comment about wealthsimple chequing",
        "rating": rating,
        "comment_date": "2026-03-01",
        "collected_at": "2026-03-02T00:00:00+00:00",
        "likes_or_upvotes": 3,
        "reply_count": 0,
        "parent_comment_id": "",
        "brand": "Wealthsimple",
        "product": "Wealthsimple App (general)",
        "campaign_or_event": "[TEST FIXTURE]",
        "raw_status": "COLLECTED",
    }
    apply_quality_flags([row])
    return row


def test_manual_review_csv_front_columns_and_blank_behavioral_fields(tmp_path):
    rows = [_cleaned_fixture_row("google_play", rating=5), _cleaned_fixture_row("reddit", subreddit="Wealthsimple", record_type="POST")]
    output_path = tmp_path / "combined_manual_review.csv"
    n = build_manual_review_csv(rows, output_path)
    assert n == 2

    import csv as csv_module
    with open(output_path, newline="", encoding="utf-8-sig") as f:
        reader = csv_module.DictReader(f)
        assert reader.fieldnames[: len(MANUAL_REVIEW_FRONT_FIELDS)] == MANUAL_REVIEW_FRONT_FIELDS
        review_rows = list(reader)

    gp_row = next(r for r in review_rows if r["Platform"] == "google_play")
    reddit_row = next(r for r in review_rows if r["Platform"] == "reddit")
    assert gp_row["Rating_or_Score"] == "5"
    assert reddit_row["Subreddit"] == "Wealthsimple"
    assert gp_row["Original_Text"] == "[TEST FIXTURE] a comment about wealthsimple chequing"

    # behavioral-analysis columns must not exist in this file at all --
    # only collection/cleaning metadata + blank human-fill-in columns
    for forbidden in ("sentiment", "emotion", "trigger", "mechanism", "behavioral_outcome", "hypothesis"):
        assert forbidden not in reader.fieldnames

    for human_field in ("human_read", "human_keep", "interesting_comment", "possible_switching_signal"):
        assert gp_row[human_field] == ""
        assert reddit_row[human_field] == ""


def test_manual_review_csv_duplicate_flag_present_but_row_not_removed(tmp_path):
    row_a = _cleaned_fixture_row("google_play", rating=4)
    row_b = _cleaned_fixture_row("google_play", rating=4)
    row_b["comment_id"] = "google_play_2"
    apply_quality_flags([row_a, row_b])  # re-flag together so exact-dup detection sees both

    output_path = tmp_path / "gp_manual_review.csv"
    n = build_manual_review_csv([row_a, row_b], output_path)
    assert n == 2  # duplicate is FLAGGED, never removed from the manual-review file
