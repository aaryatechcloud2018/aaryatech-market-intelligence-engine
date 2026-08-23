"""
Build the human-review CSV from the master cleaned dataset: a fixed column
subset (schema.HUMAN_REVIEW_FIELDS) with the human-fill-in columns always
blank. Excel/Sheets-friendly plain CSV, UTF-8 with a BOM so accented
characters (French-language comments, names) display correctly when opened
directly in Excel.
"""

from __future__ import annotations

import csv
from pathlib import Path

from src.audience_collection.schema import (
    HUMAN_FILL_IN_FIELDS,
    HUMAN_REVIEW_FIELDS,
    MANUAL_REVIEW_TECHNICAL_FIELDS,
    MANUAL_REVIEW_V2_FIELDS,
)


def _rating_or_score(row: dict) -> str:
    rating = row.get("rating", "")
    if rating not in (None, ""):
        return rating
    return row.get("likes_or_upvotes", "")


def build_manual_review_csv(cleaned_rows: list[dict], output_path: Path) -> int:
    """Build one of the v2 manual-review CSVs (Google Play / Reddit /
    combined) from a list of already-cleaned row dicts. Column order:
    9 human-friendly renamed columns first (Platform, Date, Author,
    Original_Text, Rating_or_Score, Thread_Title, Subreddit, Source_URL,
    Quality_Status), then full technical metadata, then blank
    human-fill-in columns. UTF-8 with BOM so Excel renders accented text
    correctly. Behavioral-analysis columns are never auto-filled."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=MANUAL_REVIEW_V2_FIELDS)
        writer.writeheader()
        for row in cleaned_rows:
            out_row = {
                "Platform": row.get("platform", ""),
                "Date": row.get("comment_date", ""),
                "Author": row.get("public_username", ""),
                "Original_Text": row.get("comment_text", ""),
                "Rating_or_Score": _rating_or_score(row),
                "Thread_Title": row.get("thread_or_page_title", ""),
                "Subreddit": row.get("subreddit", ""),
                "Source_URL": row.get("source_url", ""),
                "Quality_Status": row.get("quality_status", ""),
            }
            for field in MANUAL_REVIEW_TECHNICAL_FIELDS:
                out_row[field] = row.get(field, "")
            for field in HUMAN_FILL_IN_FIELDS:
                out_row[field] = ""  # never auto-filled -- human fills these in later
            writer.writerow(out_row)

    return len(cleaned_rows)


def build_human_review_csv(master_path: Path, output_path: Path) -> int:
    """Read master_path, write output_path with only HUMAN_REVIEW_FIELDS
    columns, human-fill-in columns blank. Returns the row count written."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not master_path.exists():
        with open(output_path, "w", newline="", encoding="utf-8-sig") as out_f:
            csv.DictWriter(out_f, fieldnames=HUMAN_REVIEW_FIELDS).writeheader()
        return 0

    with open(master_path, newline="", encoding="utf-8") as in_f:
        reader = csv.DictReader(in_f)
        rows = list(reader)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=HUMAN_REVIEW_FIELDS)
        writer.writeheader()
        for row in rows:
            out_row = {field: row.get(field, "") for field in HUMAN_REVIEW_FIELDS}
            for fill_in_field in HUMAN_FILL_IN_FIELDS:
                out_row[fill_in_field] = ""
            writer.writerow(out_row)

    return len(rows)
