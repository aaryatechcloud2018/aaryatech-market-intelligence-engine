"""
Phase 3 CLI entry point.

    SILVER MASTER DATABASE
            |
            +-- analysis_ready_observations.csv
            |
            +-- low_confidence_review.csv
                    |
            low_confidence_metric_summary.csv

Usage (from the project root):

    python scripts/run_phase3_review.py

Reads the existing Silver-layer fact_observation rows produced by
Phase 2, classifies each into a review status, assigns a candidate
metric name and review priority, and writes the Phase 3 CSV exports.
Nothing is deleted or overwritten in the Silver database - this is a
read-only export layer on top of it.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.normalization.phase3_review import run_phase3_review


def main() -> None:
    print("=" * 70)
    print("PHASE 3: LOW-CONFIDENCE DATA RECOVERY AND ANALYSIS-READY EXPORT")
    print("=" * 70)

    result = run_phase3_review()

    if not result:
        print("\nNo Silver-layer observations found. Run Phase 1 + Phase 2 first:")
        print("  python scripts/run_phase1_pdf_pipeline.py")
        print("  python scripts/run_phase2_normalization.py")
        return

    q = result["quality_summary"]
    print(f"\n1. Total observations           : {result['total_observations']}")
    print(f"2. Analysis-ready observations   : {q['analysis_ready']}")
    print(f"3. Needs-review observations     : {q['needs_review']}")
    print(f"4. Duplicate observations        : {q['duplicates']}")
    print(f"5. Conflicting observations      : {q['conflicts']}")
    print(f"6. Insufficient-context obs.     : {q['insufficient_context']}")
    print(f"7. Number of named metrics       : {result['named_metrics']}")
    print(f"8. UNKNOWN_METRIC records        : {result['unknown_metric_count']}")

    print(f"\n9. Top 20 low-confidence metrics:")
    for name, count in result["top_low_confidence_metrics"]:
        print(f"      {count:>4}  {name}")

    p = result["priority_counts"]
    print(f"\n10. P1 review count              : {p['P1']}")
    print(f"11. P2 review count              : {p['P2']}")
    print(f"12. P3 review count              : {p['P3']}")

    print(f"\n13. Files created:")
    for name, path in result["output_files"].items():
        print(f"      {name:<28}: {path}")

    print(f"\n    (confidence breakdown: high={q['high_confidence']}, "
          f"medium={q['medium_confidence']}, low={q['low_confidence']})")


if __name__ == "__main__":
    main()
