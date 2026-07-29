"""
Phase 4 CLI entry point.

    SILVER MASTER DATABASE (analysis_ready_observations.csv)
            |
            +-- market_kpis.csv
            +-- metric_trends.csv
            +-- business_performance.csv
            +-- hypothesis_results.csv
            +-- data_quality_summary.csv
            +-- analytics_catalog.csv

Usage (from the project root):

    python scripts/run_phase4_analytics.py

Reads ONLY data/silver/analysis_ready_observations.csv (plus the
existing Phase 2/3 quality-summary CSVs for context) and writes the
Gold-layer, Power BI-ready CSVs to data/gold/powerbi/. Never opens the
SQLite database - Bronze/Silver data and the underlying 417
observations cannot be modified by this script.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.analytics.phase4_pipeline import run_phase4_analytics
from src.config import GOLD_POWERBI_DIR


def main() -> None:
    print("=" * 70)
    print("PHASE 4: MARKET INTELLIGENCE ANALYTICS MVP")
    print("=" * 70)

    result = run_phase4_analytics()

    print(f"\n1. Analysis-ready observations used : {result['analysis_ready_observations_used']}")
    print(f"2. KPIs generated                   : {result['kpis_generated']}")
    print(f"3. Valid trend analyses              : {result['valid_trend_analyses']}")
    print(f"4. Hypothesis tests attempted        : {result['hypothesis_tests_attempted']}")
    print(f"5. Statistically valid tests          : {result['hypothesis_tests_valid']}")
    print(f"6. Tests marked INSUFFICIENT_DATA     : {result['hypothesis_tests_insufficient']}")

    print(f"\n7. Main metrics available for Power BI ({len(result['main_metrics'])}):")
    for name in result["main_metrics"]:
        print(f"      - {name}")

    print(f"\n8. Power BI files created:")
    for name, path in result["output_files"].items():
        print(f"      {name:<22}: {path}")

    print(f"\n    Gold output directory: {GOLD_POWERBI_DIR}")


if __name__ == "__main__":
    main()
