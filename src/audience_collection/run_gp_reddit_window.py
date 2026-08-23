"""
Runs Google Play + Reddit collection for the current research window
(config.COLLECTION_WINDOW_START/END -- currently 2026-02-01 to 2026-07-31),
cleans each platform, and builds the three manual-review CSVs:

  data/audience/human_review/wealthsimple_google_play_feb_jul_2026_manual_review.csv
  data/audience/human_review/wealthsimple_reddit_feb_jul_2026_manual_review.csv
  data/audience/human_review/wealthsimple_combined_feb_jul_2026_manual_review.csv

Does NOT touch App Store or YouTube, and does NOT touch the original
run_collection.py (all-4-platforms, Oct-Dec 2024) flow or its files.

Run from a machine/environment with real internet access:

    python -m src.audience_collection.run_gp_reddit_window

Google Play needs no credentials. Reddit needs REDDIT_CLIENT_ID and
REDDIT_CLIENT_SECRET in your local .env file -- if they're missing, this
script reports exactly what's needed and skips Reddit rather than
attempting (and failing) the now-blocked unauthenticated endpoints. Google
Play still runs either way.

Safe to re-run: raw files only ever gain new rows (append-only, never
overwritten/deleted); cleaned/manual-review files are fully regenerated
derived output each run.
"""

from __future__ import annotations

import sys
from collections import Counter

from src.audience_collection import config
from src.audience_collection.cleaning.clean_pipeline import clean_platform
from src.audience_collection.collectors import google_play_collector, reddit_collector
from src.audience_collection.collectors.base import append_new_raw_rows
from src.audience_collection.human_review import build_manual_review_csv

COLLECTORS = {
    "google_play": google_play_collector,
    "reddit": reddit_collector,
}


def run() -> dict:
    config.ensure_directories()
    window_start = config.COLLECTION_WINDOW_START
    window_end = config.COLLECTION_WINDOW_END

    print(f"Stage 2 collection window: {window_start} to {window_end}")
    print(f"Company: {config.BRAND}")
    print(f"Business context: {config.CAMPAIGN_OR_EVENT}\n")

    raw_reports: dict[str, dict] = {}
    cleaned_rows_by_platform: dict[str, list[dict]] = {}
    status_counts_by_platform: dict[str, Counter] = {}

    for platform, collector in COLLECTORS.items():
        print(f"--- Collecting {platform} ---")
        raw_path = config.raw_path_for(platform, window_start, window_end)
        cleaned_path = config.cleaned_path_for(platform, window_start, window_end)

        try:
            rows = collector.collect(window_start, window_end)
        except Exception as exc:  # noqa: BLE001 -- report and continue with the other platform
            print(f"  SKIPPED: {type(exc).__name__}: {exc}")
            raw_reports[platform] = {"error": str(exc)}
            cleaned_rows_by_platform[platform] = []
            status_counts_by_platform[platform] = Counter()
            continue

        report = append_new_raw_rows(raw_path, rows)
        raw_reports[platform] = report
        print(f"  collected {len(rows)} rows this run -> {report}")
        print(f"  raw file: {raw_path}")

        cleaned_rows = clean_platform(raw_path, cleaned_path)
        cleaned_rows_by_platform[platform] = cleaned_rows
        status_counts_by_platform[platform] = Counter(r["quality_status"] for r in cleaned_rows)
        print(f"  cleaned file: {cleaned_path} ({len(cleaned_rows)} rows)")

    print("\n--- Manual-review CSVs ---")
    gp_rows = cleaned_rows_by_platform.get("google_play", [])
    reddit_rows = cleaned_rows_by_platform.get("reddit", [])
    combined_rows = gp_rows + reddit_rows

    build_manual_review_csv(gp_rows, config.GOOGLE_PLAY_REVIEW_FILE)
    print(f"  Google Play: {len(gp_rows)} rows -> {config.GOOGLE_PLAY_REVIEW_FILE}")
    build_manual_review_csv(reddit_rows, config.REDDIT_REVIEW_FILE)
    print(f"  Reddit: {len(reddit_rows)} rows -> {config.REDDIT_REVIEW_FILE}")
    build_manual_review_csv(combined_rows, config.COMBINED_REVIEW_FILE)
    print(f"  Combined: {len(combined_rows)} rows -> {config.COMBINED_REVIEW_FILE}")

    summary = {
        "window": (window_start, window_end),
        "raw_reports": raw_reports,
        "cleaned_counts": {p: len(r) for p, r in cleaned_rows_by_platform.items()},
        "status_counts": {p: dict(c) for p, c in status_counts_by_platform.items()},
        "total_combined_rows": len(combined_rows),
    }

    print("\n=== Summary ===")
    for platform in COLLECTORS:
        print(f"{platform}: {summary['cleaned_counts'].get(platform, 0)} cleaned rows, "
              f"status breakdown: {summary['status_counts'].get(platform, {})}")
    print(f"Combined manual-review rows: {summary['total_combined_rows']}")

    return summary


if __name__ == "__main__":
    run()
    sys.exit(0)
