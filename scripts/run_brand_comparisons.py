"""
Simple brand comparison tables for Power BI.

Usage (from the project root):

    python scripts/run_brand_comparisons.py

Reads ONLY data/gold/powerbi/market_kpis.csv and metric_trends.csv
(unchanged by this script) and writes simple "brand vs value" CSVs to
data/gold/powerbi/brand_comparisons/ - one per KPI that already has 2+
brands compared in metric_trends.csv, plus a combined
brand_kpi_comparisons.csv. No filtering, validation, or new
calculations are performed; brand names are normalized per a fixed,
simple mapping only.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.analytics.brand_comparisons import run_brand_comparisons


def main() -> None:
    print("=" * 70)
    print("BRAND COMPARISON TABLES FOR POWER BI")
    print("=" * 70)

    result = run_brand_comparisons()

    print()
    for entry in result["created_files"]:
        print(f"{entry['file']}")
        print(f"    rows : {entry['row_count']}")
        print(f"    brands: {', '.join(entry['brands'])}")
        print()


if __name__ == "__main__":
    main()
