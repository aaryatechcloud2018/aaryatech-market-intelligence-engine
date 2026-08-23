"""
Shared helpers for all Stage 2 collectors: consistent comment IDs and an
append-only raw-file writer that can never lose or overwrite existing rows.
"""

from __future__ import annotations

import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from src.audience_collection.schema import RAW_FIELDS


def make_comment_id(platform: str, native_id: str) -> str:
    """Build a stable, globally-unique comment_id from a platform's own ID."""
    return f"{platform}_{native_id}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_new_raw_rows(path: Path, new_rows: list[dict]) -> dict:
    """Write new_rows into the raw CSV at `path` WITHOUT ever overwriting or
    deleting anything already there.

    - If the file does not exist, it is created with the new rows.
    - If it exists, every existing row is preserved byte-for-byte in content
      (re-written verbatim); only rows whose comment_id is not already
      present are appended.
    - Returns a small report: {"existing": N, "appended": N, "skipped_duplicate_id": N}.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    existing_rows: list[dict] = []
    existing_ids: set[str] = set()
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_rows.append(row)
                existing_ids.add(row["comment_id"])

    rows_to_append = []
    skipped = 0
    for row in new_rows:
        if row["comment_id"] in existing_ids:
            skipped += 1
            continue
        rows_to_append.append(row)
        existing_ids.add(row["comment_id"])

    all_rows = existing_rows + rows_to_append
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RAW_FIELDS)
        writer.writeheader()
        for row in all_rows:
            writer.writerow({field: row.get(field, "") for field in RAW_FIELDS})

    return {
        "existing": len(existing_rows),
        "appended": len(rows_to_append),
        "skipped_duplicate_id": skipped,
        "total": len(all_rows),
    }


def empty_raw_row() -> dict:
    """A raw row dict with every required field present (blank strings),
    so a collector only has to set the fields it actually has."""
    return {field: "" for field in RAW_FIELDS}
