"""
Single source of truth for the Stage 2 audience data field lists.

Every collector, the cleaning pipeline, the merge step, and the human-review
CSV builder import these lists rather than hard-coding column names, so the
schema only has to change in one place.
"""

from __future__ import annotations

# Fields every raw record must preserve, regardless of platform.
#
# v2 additions (record_type, subreddit, post_id, rating) support Reddit's
# post-vs-comment structure and keep star ratings out of comment_text (the
# original v1 Google Play/App Store collectors embedded "[Rating: X/5]" into
# comment_text, which technically mutated the original text -- fixed here).
# Fields that don't apply to a given platform are simply left blank ("").
RAW_FIELDS: list[str] = [
    "comment_id",
    "record_type",  # REVIEW (Play/App Store) | POST | COMMENT (Reddit/YouTube)
    "platform",
    "subreddit",  # Reddit only; blank elsewhere
    "post_id",  # Reddit: native thread ID (shared by a post and its comments); blank elsewhere
    "source_url",
    "thread_or_page_title",
    "public_username",
    "comment_text",  # ALWAYS the original text, verbatim -- never prefixed/mutated
    "rating",  # star rating (Google Play/App Store, 1-5); blank elsewhere
    "comment_date",
    "collected_at",
    "likes_or_upvotes",
    "reply_count",
    "parent_comment_id",
    "brand",
    "product",
    "campaign_or_event",
    "raw_status",
]

# Fields added during cleaning/quality-flagging. Never present in raw files.
QUALITY_FIELDS: list[str] = [
    "is_exact_duplicate",
    "near_duplicate_score",
    "possible_spam",
    "possible_bot",
    "possible_coordinated_post",
    "low_information",
    "irrelevant",
    "language",
    "quality_status",
    "cleaned_text",
]

# A processed/cleaned record = raw fields + quality fields, in this order.
CLEANED_FIELDS: list[str] = RAW_FIELDS + QUALITY_FIELDS

# Allowed values for quality_status. UNCERTAIN is the honest default when
# flags conflict or evidence is thin -- never force a confident label.
QUALITY_STATUS_VALUES: list[str] = [
    "VALID",
    "LOW_INFORMATION",
    "DUPLICATE",
    "POSSIBLE_SPAM",
    "POSSIBLE_BOT",
    "POSSIBLE_COORDINATED",
    "IRRELEVANT",
    "UNCERTAIN",
]

# Exact column set/order for the human-review CSV. A subset of the master
# dataset's columns, plus blank human-fill-in columns.
HUMAN_REVIEW_FIELDS: list[str] = [
    "comment_id",
    "platform",
    "comment_date",
    "public_username",
    "comment_text",
    "source_url",
    "likes_or_upvotes",
    "reply_count",
    "quality_status",
    "is_exact_duplicate",
    "near_duplicate_score",
    "possible_spam",
    "possible_bot",
    "possible_coordinated_post",
    "low_information",
    "irrelevant",
    "human_read",
    "human_keep",
    "human_notes",
    "interesting_comment",
    "possible_buyer_signal",
    "possible_switching_signal",
    "possible_community_signal",
]

# These columns are always blank in a freshly generated human-review CSV --
# they exist for the human reviewer to fill in manually.
HUMAN_FILL_IN_FIELDS: list[str] = [
    "human_read",
    "human_keep",
    "human_notes",
    "interesting_comment",
    "possible_buyer_signal",
    "possible_switching_signal",
    "possible_community_signal",
]

# --- v2 manual-review CSVs (per data/audience/human_review/*_manual_review.csv) ---
# Human-friendly column names/order for reading in Excel: the 9 columns a
# person actually needs to read a comment come first (renamed from the raw
# snake_case field names), then full technical metadata, then the blank
# human-fill-in columns. Used by human_review.py::build_manual_review_csv.

# (output column name, source field in a CLEANED_FIELDS row, or None if computed)
MANUAL_REVIEW_FRONT_FIELDS: list[str] = [
    "Platform",
    "Date",
    "Author",
    "Original_Text",
    "Rating_or_Score",
    "Thread_Title",
    "Subreddit",
    "Source_URL",
    "Quality_Status",
]

# Everything else worth keeping, original field names, technical audience.
MANUAL_REVIEW_TECHNICAL_FIELDS: list[str] = [
    "comment_id",
    "record_type",
    "post_id",
    "parent_comment_id",
    "likes_or_upvotes",
    "reply_count",
    "rating",
    "is_exact_duplicate",
    "near_duplicate_score",
    "possible_spam",
    "possible_bot",
    "possible_coordinated_post",
    "low_information",
    "irrelevant",
    "language",
    "brand",
    "product",
    "campaign_or_event",
    "raw_status",
    "collected_at",
]

MANUAL_REVIEW_V2_FIELDS: list[str] = (
    MANUAL_REVIEW_FRONT_FIELDS + MANUAL_REVIEW_TECHNICAL_FIELDS + HUMAN_FILL_IN_FIELDS
)
