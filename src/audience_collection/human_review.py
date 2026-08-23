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

from src.audience_collection.schema import HUMAN_FILL_IN_FIELDS, HUMAN_REVIEW_FIELDS


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
