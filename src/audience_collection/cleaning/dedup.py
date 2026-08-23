"""
Duplicate detection, handled as three separate, non-destructive signals
(per Stage 2 instructions -- never auto-delete a repeated narrative, since
it might be genuine consensus, an information cascade, or coordinated
amplification rather than noise):

1. Exact duplicates -- identical normalized text -> is_exact_duplicate.
2. Near duplicates -- high textual similarity -> near_duplicate_score.
3. Cross-user repeated narratives (near-duplicate text from >=2 different
   usernames) -- a signal for quality_flags.possible_coordinated_post to
   pick up; this module only exposes the grouping, it does not judge intent.
"""

from __future__ import annotations

from difflib import SequenceMatcher

from src.audience_collection.cleaning.text_utils import normalize_for_dedup
from src.audience_collection.config import NEAR_DUPLICATE_SIMILARITY_THRESHOLD


def flag_exact_duplicates(rows: list[dict]) -> None:
    """Mutates rows in place, setting is_exact_duplicate on every row after
    the first occurrence of a given normalized text (within the same
    platform). The first occurrence is left as an original, not a duplicate."""
    seen: dict[tuple[str, str], bool] = {}
    for row in rows:
        key = (row["platform"], normalize_for_dedup(row["comment_text"]))
        if key in seen:
            row["is_exact_duplicate"] = True
        else:
            row["is_exact_duplicate"] = False
            seen[key] = True


def compute_near_duplicate_groups(rows: list[dict]) -> list[list[int]]:
    """Return groups (lists of row indexes into `rows`) whose normalized text
    similarity is >= NEAR_DUPLICATE_SIMILARITY_THRESHOLD, compared within the
    same platform only. A row can appear in at most one group (first match
    wins) -- good enough for flagging purposes, not a formal clustering
    algorithm."""
    normalized = [normalize_for_dedup(r["comment_text"]) for r in rows]
    grouped = [False] * len(rows)
    groups: list[list[int]] = []

    for i in range(len(rows)):
        if grouped[i] or not normalized[i]:
            continue
        group = [i]
        for j in range(i + 1, len(rows)):
            if grouped[j] or not normalized[j]:
                continue
            if rows[i]["platform"] != rows[j]["platform"]:
                continue
            # cheap length pre-filter before the more expensive ratio() call
            len_i, len_j = len(normalized[i]), len(normalized[j])
            if len_i == 0 or len_j == 0:
                continue
            if min(len_i, len_j) / max(len_i, len_j) < NEAR_DUPLICATE_SIMILARITY_THRESHOLD:
                continue
            similarity = SequenceMatcher(None, normalized[i], normalized[j]).ratio()
            if similarity >= NEAR_DUPLICATE_SIMILARITY_THRESHOLD:
                group.append(j)
                grouped[j] = True
        if len(group) > 1:
            grouped[i] = True
            groups.append(group)

    return groups


def apply_near_duplicate_scores(rows: list[dict]) -> list[list[int]]:
    """Mutates rows in place, setting near_duplicate_score (0.0 by default,
    or the group's internal similarity for grouped rows). Returns the
    groups so callers (e.g. the coordinated-post heuristic) can reuse them
    without recomputing."""
    for row in rows:
        row["near_duplicate_score"] = 0.0

    groups = compute_near_duplicate_groups(rows)
    normalized = [normalize_for_dedup(r["comment_text"]) for r in rows]

    for group in groups:
        base = normalized[group[0]]
        for idx in group:
            score = SequenceMatcher(None, base, normalized[idx]).ratio()
            rows[idx]["near_duplicate_score"] = round(max(rows[idx]["near_duplicate_score"], score), 3)
        rows[group[0]]["near_duplicate_score"] = 1.0

    return groups
