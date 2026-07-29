"""
Phase 4.1 CLI entry point: Executive Intelligence Layer.

Usage (from the project root):

    python scripts/run_phase4_1_executive_layer.py

Reads ONLY data/gold/powerbi/market_kpis.csv and metric_trends.csv and
writes two new files to the same directory:

    executive_kpi_snapshot.csv
    executive_trend_summary.csv

Does not modify any existing Phase 1-4 file. See
src/analytics/executive_layer.py for the period-reliability audit this
module's filtering is based on.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.analytics.executive_layer import run_phase4_1


def main() -> None:
    print("=" * 70)
    print("PHASE 4.1: EXECUTIVE INTELLIGENCE LAYER")
    print("=" * 70)

    result = run_phase4_1()

    print(f"\nKPI rows created                         : {result['kpi_rows_created']}")
    print(f"Trend rows created                        : {result['trend_rows_created']}")
    print(f"KPI rows excluded (unreliable period)     : {result['kpi_rows_excluded_unreliable_period']}")
    print(f"KPI rows excluded (semantic mismatch)     : {result['kpi_rows_excluded_semantic_mismatch']}")
    print(f"KPI rows excluded (competitor-attributed) : {result['kpi_rows_excluded_competitor']}")
    print(f"Trend rows excluded (unreliable period)   : {result['trend_rows_excluded_unreliable_period']}")

    print(f"\nKPI names excluded due to period unreliability:")
    for name in result["excluded_kpi_names"]:
        print(f"      - {name}")

    print(f"\nTrends excluded due to period unreliability:")
    for name in result["excluded_trend_names"]:
        print(f"      - {name}")

    print(f"\nFiles created:")
    for name, path in result["output_files"].items():
        print(f"      {name:<28}: {path}")


if __name__ == "__main__":
    main()
