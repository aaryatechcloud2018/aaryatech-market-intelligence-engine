"""
Per-platform cleaning: read a raw CSV, apply quality flags, write the
cleaned CSV. Raw files are only ever read here, never modified -- cleaned
files are fully regenerable derived output, so overwriting a *_cleaned.csv
on a re-run is fine (unlike raw files, which must never be overwritten).
"""

from __future__ import annotations

import csv
from pathlib import Path

from src.audience_collection.cleaning.quality_flags import apply_quality_flags
from src.audience_collection.schema import CLEANED_FIELDS


def read_raw_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def clean_platform(raw_path: Path, cleaned_path: Path) -> list[dict]:
    """Read raw_path, apply quality flags, write cleaned_path. Returns the
    cleaned rows (also useful for the merge step without a re-read)."""
    rows = read_raw_csv(raw_path)
    apply_quality_flags(rows)

    cleaned_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cleaned_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CLEANED_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CLEANED_FIELDS})

    return rows
