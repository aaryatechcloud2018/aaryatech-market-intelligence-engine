"""
Stage 2 orchestrator: run all four collectors, clean each platform, merge
into the master dataset, and build the human-review CSV -- printing a
per-platform summary report at the end.

Run once network access to Reddit / Google Play / Apple App Store / YouTube
is available from this environment:

    python -m src.audience_collection.run_collection

Safe to re-run: raw files only ever gain new rows (append_new_raw_rows never
overwrites/deletes existing ones); cleaned/master/human-review files are
fully regenerated derived output each run, which is expected and safe.
"""

from __future__ import annotations

import sys
from collections import Counter

from src.audience_collection import config
from src.audience_collection.cleaning.clean_pipeline import clean_platform
from src.audience_collection.collectors import (
    app_store_collector,
    google_play_collector,
    reddit_collector,
    youtube_collector,
)
from src.audience_collection.collectors.base import append_new_raw_rows
from src.audience_collection.human_review import build_human_review_csv
from src.audience_collection.merge import merge_cleaned_files

COLLECTORS = {
    "reddit": reddit_collector,
    "google_play": google_play_collector,
    "app_store": app_store_collector,
    "youtube": youtube_collector,
}


def run() -> None:
    config.ensure_directories()
    window_start = config.COLLECTION_WINDOW_START
    window_end = config.COLLECTION_WINDOW_END

    print(f"Stage 2 collection window: {window_start} to {window_end}")
    print(f"Campaign/event context: {config.CAMPAIGN_OR_EVENT}\n")

    raw_reports: dict[str, dict] = {}
    for platform, collector in COLLECTORS.items():
        print(f"--- Collecting {platform} ---")
        try:
            rows = collector.collect(window_start, window_end)
        except Exception as exc:  # noqa: BLE001 -- report and continue with other platforms
            print(f"  FAILED: {platform} collection raised {type(exc).__name__}: {exc}")
            raw_reports[platform] = {"error": str(exc)}
            continue
        report = append_new_raw_rows(config.RAW_FILES[platform], rows)
        raw_reports[platform] = report
        print(f"  collected {len(rows)} rows this run -> {report}")

    print("\n--- Cleaning ---")
    cleaned_counts: dict[str, int] = {}
    status_counts: Counter = Counter()
    for platform in COLLECTORS:
        cleaned_rows = clean_platform(config.RAW_FILES[platform], config.CLEANED_FILES[platform])
        cleaned_counts[platform] = len(cleaned_rows)
        status_counts.update(row["quality_status"] for row in cleaned_rows)
        print(f"  {platform}: {len(cleaned_rows)} cleaned rows")

    print("\n--- Merging ---")
    merge_counts = merge_cleaned_files(config.CLEANED_FILES, config.MASTER_CLEANED_FILE)
    total_master_rows = sum(merge_counts.values())
    print(f"  master dataset: {total_master_rows} rows -> {config.MASTER_CLEANED_FILE}")

    print("\n--- Human review CSV ---")
    review_rows = build_human_review_csv(config.MASTER_CLEANED_FILE, config.HUMAN_REVIEW_FILE)
    print(f"  {review_rows} rows -> {config.HUMAN_REVIEW_FILE}")

    print("\n=== Stage 2 summary ===")
    print(f"Raw rows collected this run: { {p: r.get('appended', 0) for p, r in raw_reports.items()} }")
    print(f"Cleaned rows per platform: {cleaned_counts}")
    print(f"Quality status breakdown: {dict(status_counts)}")
    print(f"Total master rows: {total_master_rows}")
    print(f"Total human-review rows: {review_rows}")

    if total_master_rows < config.TARGET_MIN_ROWS:
        print(
            f"\nNOTE: total rows ({total_master_rows}) is below the V1 target "
            f"of {config.TARGET_MIN_ROWS}-{config.TARGET_MAX_ROWS}. This is not "
            f"an error -- document the shortfall per-platform rather than "
            f"inflating the window or fabricating rows."
        )


if __name__ == "__main__":
    run()
    sys.exit(0)
