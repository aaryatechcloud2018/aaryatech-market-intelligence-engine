"""
Phase 2 CLI entry point.

    BRONZE -> TABLE CLASSIFICATION -> RELEVANCE SCORING -> METRIC
    EXTRACTION -> NORMALIZATION -> ENTITY RESOLUTION -> PROVENANCE
    -> SILVER MASTER DATABASE

Usage (from the project root):

    python scripts/run_phase2_normalization.py

Reads the Bronze-layer tables already loaded into SQLite by Phase 1
(scripts/run_phase1_pdf_pipeline.py), classifies every table, extracts
structured metric observations from relevant ones, normalizes and
resolves entities, runs quality control, and writes the Silver-layer
database rows + CSV/report exports. Does not summarize the document,
generate insights, or run statistics - that is a later phase.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DATABASE_PATH, SILVER_OBSERVATIONS_DIR, SILVER_REPORTS_DIR
from src.normalization.phase2_pipeline import run_phase2_normalization


def main() -> None:
    print("=" * 70)
    print("PHASE 2: TABLE CLASSIFICATION + NORMALIZATION -> SILVER DATABASE")
    print("=" * 70)

    results = run_phase2_normalization()

    if not results:
        print("\nNo successfully-extracted documents found. Run Phase 1 first:")
        print("  python scripts/run_phase1_pdf_pipeline.py")
        return

    for r in results:
        print("\n" + "-" * 70)
        print(f"DOCUMENT: {r['file_name']}  (document_id={r['document_id']})")
        print(f"  Detected subject company : {r['document_subject_company'] or '(not detected in text)'}")
        print(f"  Tables total             : {r['tables_total']}")
        print(f"  Tables classified        : {r['tables_classified']}")
        print(f"  Tables relevant          : {r['tables_relevant']}")
        print(f"  Tables irrelevant        : {r['tables_irrelevant']}")
        print(f"  Category breakdown       :")
        for cat, count in sorted(r["category_counts"].items(), key=lambda kv: -kv[1]):
            print(f"      {cat:<12} : {count}")
        print(f"  Observations created     : {r['observations_created']}")
        print(f"  High-confidence obs      : {r['high_confidence_observations']}")
        print(f"  Low-confidence obs       : {r['low_confidence_observations']}")
        print(f"  Duplicate groups found   : {r['duplicates_detected']}")
        print(f"  Conflicting groups found : {r['conflicts_detected']}")
        print(f"  Unique entities          : {r['unique_entities']}")
        print(f"  Unique metrics           : {r['unique_metrics']}")
        print(f"  Unique geographies       : {r['unique_geographies']}")
        print(f"  Output files:")
        for name, path in r["output_files"].items():
            print(f"      {name:<28}: {path}")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Database              : {DATABASE_PATH}")
    print(f"  Silver observations   : {SILVER_OBSERVATIONS_DIR}")
    print(f"  Silver reports        : {SILVER_REPORTS_DIR}")
    print(f"  Documents processed   : {len(results)}")


if __name__ == "__main__":
    main()
