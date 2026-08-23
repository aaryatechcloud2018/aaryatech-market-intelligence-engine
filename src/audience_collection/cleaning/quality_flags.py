"""
Quality-flagging heuristics. Every flag is a boolean SIGNAL, not a verdict --
in particular possible_bot and possible_coordinated_post never claim
certainty (see docstrings below for the exact reasoning behind each flag,
since the shared schema has no separate "reason" column).

Nothing in this module deletes or excludes a row. quality_status summarizes
the flags into one of schema.QUALITY_STATUS_VALUES for readability, but the
underlying boolean columns remain available for a human reviewer to
override that summary.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from src.audience_collection.cleaning.dedup import apply_near_duplicate_scores, flag_exact_duplicates
from src.audience_collection.cleaning.text_utils import clean_text, guess_language, normalize_for_dedup
from src.audience_collection.config import LOW_INFORMATION_MIN_CHARS, LOW_INFORMATION_MIN_WORDS

_URL_RE = re.compile(r"https?://\S+")
_SPAM_KEYWORDS = [
    "referral code", "promo code", "use my code", "sign up with my link",
    "dm me", "click here", "free money", "make money fast", "check my bio",
    "whatsapp me", "telegram me", "investment opportunity guaranteed",
]
_REPEATED_PUNCT_RE = re.compile(r"([!$?])\1{3,}")

# Reason: usernames that are default-generated-looking (long digit runs,
# or the literal words bot/auto) are a weak but real signal of automated
# accounts. This is a HEURISTIC, not a verified bot detection -- flagged as
# possible_bot, never asserted as fact.
_BOT_USERNAME_RE = re.compile(r"(bot\d*$|_bot$|^auto[-_]?mod)", re.IGNORECASE)
_DIGIT_HEAVY_USERNAME_RE = re.compile(r"^[A-Za-z]+\d{5,}$")

BRAND_KEYWORDS = ["wealthsimple", "wealth simple", " ws ", "ws app"]


def _looks_like_bot_username(username: str) -> bool:
    if not username:
        return False
    if _BOT_USERNAME_RE.search(username):
        return True
    if _DIGIT_HEAVY_USERNAME_RE.match(username):
        return True
    return False


def flag_possible_spam(text: str) -> bool:
    """Reason surfaced here (no dedicated column): flags text containing
    >=2 URLs, OR a known promotional phrase, OR excessive repeated
    punctuation (!!!!/$$$$), all common markers of promotional/spam posts
    rather than genuine product feedback."""
    if len(_URL_RE.findall(text)) >= 2:
        return True
    lowered = text.lower()
    if any(keyword in lowered for keyword in _SPAM_KEYWORDS):
        return True
    if _REPEATED_PUNCT_RE.search(text):
        return True
    return False


def flag_low_information(cleaned: str) -> bool:
    word_count = len(cleaned.split())
    return len(cleaned) < LOW_INFORMATION_MIN_CHARS or word_count < LOW_INFORMATION_MIN_WORDS


def flag_irrelevant(platform: str, text: str) -> bool:
    """Google Play / App Store rows are reviews of the app itself, so they
    are always on-topic by construction. Reddit/YouTube rows are collected
    around a search term or a review video, but individual comments can go
    off-topic -- flagged irrelevant if no brand keyword appears at all."""
    if platform in ("google_play", "app_store"):
        return False
    lowered = f" {text.lower()} "
    return not any(keyword in lowered for keyword in BRAND_KEYWORDS)


def apply_quality_flags(rows: list[dict]) -> None:
    """Mutates `rows` in place, populating every QUALITY_FIELDS column.
    Must be called on a full platform batch (or the full merged batch) at
    once -- several flags (duplicates, coordinated-post) are relative to
    the rest of the batch, not computable per-row in isolation."""
    if not rows:
        return

    flag_exact_duplicates(rows)
    near_dup_groups = apply_near_duplicate_scores(rows)

    # Reason surfaced here (no dedicated column): a near-duplicate GROUP
    # (similarity >= threshold) that contains >=2 DISTINCT usernames is a
    # signal of the same narrative being repeated by different accounts --
    # this can be genuine consensus, an information cascade, or coordinated
    # amplification. We flag it and let a human/later module judge intent;
    # we never delete or assume the worst.
    coordinated_row_indexes: set[int] = set()
    for group in near_dup_groups:
        usernames = {rows[idx]["public_username"] for idx in group}
        if len(usernames) >= 2:
            coordinated_row_indexes.update(group)

    # Reason surfaced here (no dedicated column): the SAME username posting
    # >=3 near-identical comments across the collected batch is a weak
    # signal of scripted/automated posting -- flagged as possible_bot, not
    # asserted as fact. Combined with a bot-shaped username as a second,
    # independent signal.
    text_by_username: dict[str, list[int]] = defaultdict(list)
    for idx, row in enumerate(rows):
        text_by_username[row["public_username"]].append(idx)

    bot_row_indexes: set[int] = set()
    for username, idxs in text_by_username.items():
        normalized_texts = [normalize_for_dedup(rows[i]["comment_text"]) for i in idxs]
        repeat_counts = Counter(t for t in normalized_texts if t)
        if any(count >= 3 for count in repeat_counts.values()):
            bot_row_indexes.update(idxs)

    for idx, row in enumerate(rows):
        cleaned = clean_text(row["comment_text"])
        row["cleaned_text"] = cleaned
        row["language"] = guess_language(cleaned)
        row["possible_spam"] = flag_possible_spam(row["comment_text"])
        row["possible_bot"] = idx in bot_row_indexes or _looks_like_bot_username(row["public_username"])
        row["possible_coordinated_post"] = idx in coordinated_row_indexes
        row["low_information"] = flag_low_information(cleaned)
        row["irrelevant"] = flag_irrelevant(row["platform"], row["comment_text"])
        row["quality_status"] = _derive_quality_status(row)


def _derive_quality_status(row: dict) -> str:
    """First matching rule wins. UNCERTAIN is the honest fallback when
    there simply isn't enough signal either way -- never force VALID or a
    negative label without a real reason."""
    if not row.get("cleaned_text"):
        return "UNCERTAIN"
    if row["is_exact_duplicate"]:
        return "DUPLICATE"
    if row["possible_coordinated_post"]:
        return "POSSIBLE_COORDINATED"
    if row["possible_bot"]:
        return "POSSIBLE_BOT"
    if row["possible_spam"]:
        return "POSSIBLE_SPAM"
    if row["irrelevant"]:
        return "IRRELEVANT"
    if row["low_information"]:
        return "LOW_INFORMATION"
    return "VALID"
