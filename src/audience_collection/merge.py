"""
Merge the four per-platform cleaned CSVs into one master dataset. A plain
concatenation -- no row is dropped, re-flagged, or altered here; merging is
purely additive.
"""

from __future__ import annotations

import csv
from pathlib import Path

from src.audience_collection.schema import CLEANED_FIELDS


def merge_cleaned_files(cleaned_paths: dict[str, Path], master_path: Path) -> dict[str, int]:
    """Concatenate every cleaned CSV in `cleaned_paths` (platform -> path)
    into `master_path`. Returns a per-platform row-count report."""
    counts: dict[str, int] = {}
    master_path.parent.mkdir(parents=True, exist_ok=True)

    with open(master_path, "w", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=CLEANED_FIELDS)
        writer.writeheader()
        for platform, path in cleaned_paths.items():
            if not path.exists():
                counts[platform] = 0
                continue
            with open(path, newline="", encoding="utf-8") as in_f:
                reader = csv.DictReader(in_f)
                n = 0
                for row in reader:
                    writer.writerow({field: row.get(field, "") for field in CLEANED_FIELDS})
                    n += 1
                counts[platform] = n

    return counts
