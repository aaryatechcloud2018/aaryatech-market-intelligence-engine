"""
Single source of truth for the Stage 2 audience data field lists.

Every collector, the cleaning pipeline, the merge step, and the human-review
CSV builder import these lists rather than hard-coding column names, so the
schema only has to change in one place.
"""

from __future__ import annotations

# Fields every raw record must preserve, regardless of platform.
RAW_FIELDS: list[str] = [
    "comment_id",
    "platform",
    "source_url",
    "thread_or_page_title",
    "public_username",
    "comment_text",
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
