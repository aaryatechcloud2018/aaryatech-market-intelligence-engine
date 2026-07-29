"""
Simple brand comparison tables for Power BI.

Reads ONLY the two existing Gold-layer files:
  - data/gold/powerbi/market_kpis.csv
  - data/gold/powerbi/metric_trends.csv

and reshapes data ALREADY present in them into small "brand vs KPI"
tables (one row per brand, one column for the value) suitable for a
simple Power BI bar chart: brand on the X-axis, one KPI on the Y-axis.

No filtering, validation, exclusion, or quality judgment is applied -
every metric/brand combination already present in metric_trends.csv is
used exactly as found. No numeric value is changed, recalculated, or
inferred; only the brand NAME text is normalized per the fixed mapping
below, and metric names are only stripped of a "Competitor " prefix so
that, e.g., "EBITDA" (Smartworks) and "Competitor EBITDA" (Awfis) land
in the same brand-comparison table - they are the same KPI reported for
different brands, not different metrics.
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

from src.config import GOLD_POWERBI_DIR

MARKET_KPIS_CSV = GOLD_POWERBI_DIR / "market_kpis.csv"
METRIC_TRENDS_CSV = GOLD_POWERBI_DIR / "metric_trends.csv"
OUTPUT_DIR = GOLD_POWERBI_DIR / "brand_comparisons"
COMBINED_CSV = OUTPUT_DIR / "brand_kpi_comparisons.csv"

# Brand name normalization - fixed mapping, nothing inferred. Any name
# not listed here is kept exactly as-is.
BRAND_NAME_MAP: dict[str, str] = {
    "Smartworks Coworking Spaces Limited": "Smartworks",
}

_COMPETITOR_PREFIX = "Competitor "


def normalize_brand(entity_name: str) -> str:
    return BRAND_NAME_MAP.get(entity_name, entity_name)


def base_metric_name(metric_name: str) -> str:
    """Strip the 'Competitor ' prefix so the same KPI groups across brands."""
    if metric_name.startswith(_COMPETITOR_PREFIX):
        return metric_name[len(_COMPETITOR_PREFIX):]
    return metric_name


def slugify_metric(metric_name: str) -> str:
    name = re.sub(r"\(.*?\)", "", metric_name)  # drop parenthetical qualifiers, e.g. "(Loss)"
    name = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    return name


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found - run scripts/run_phase4_analytics.py first.")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _latest_observation_id(source_observation_ids: str) -> str | None:
    """metric_trends.csv stores 'start_id;end_id' - the end id is the latest period."""
    ids = [i for i in source_observation_ids.split(";") if i]
    return ids[-1] if ids else None


def build_brand_comparisons(
    trend_rows: list[dict], kpi_rows: list[dict]
) -> tuple[dict[str, list[dict]], list[dict]]:
    """
    Returns (per_metric_tables, combined_rows).
    per_metric_tables: {base_metric_name: [{"brand": ..., "value": ...}, ...]}
      - only includes metrics with 2+ distinct brands.
    combined_rows: [{"brand": ..., "kpi": ..., "value": ...}, ...]
    """
    # market_kpis.csv has both raw (directly-extracted) rows and derived
    # "X Growth" rows, and a Growth row reuses its end-period observation's
    # id as its own source_observation_id (see kpi_builder.py) - so this
    # lookup must only be built from raw rows, or a Growth row's
    # percentage value would silently overwrite the real reported value
    # for the same observation_id.
    kpi_by_observation_id = {
        row["source_observation_id"]: row for row in kpi_rows if not row["kpi_name"].endswith(" Growth")
    }

    # Group metric_trends.csv rows by base metric name first, so we can
    # tell which metrics actually have multiple brands before emitting.
    rows_by_metric: dict[str, list[dict]] = defaultdict(list)
    for row in trend_rows:
        rows_by_metric[base_metric_name(row["metric_name"])].append(row)

    per_metric_tables: dict[str, list[dict]] = {}
    combined_rows: list[dict] = []

    for metric, rows in rows_by_metric.items():
        brands_present = {normalize_brand(r["entity_name"]) for r in rows}
        if len(brands_present) < 2:
            continue  # not a brand comparison - only one brand has this metric

        table_rows: list[dict] = []
        for row in rows:
            brand = normalize_brand(row["entity_name"])

            # Prefer the exact as-reported value from market_kpis.csv for
            # this trend's latest (ending) observation; fall back to the
            # trend's own ending_value if that observation isn't found
            # there (should not normally happen, but never invents data).
            end_obs_id = _latest_observation_id(row["source_observation_ids"])
            kpi_row = kpi_by_observation_id.get(end_obs_id) if end_obs_id else None
            value = kpi_row["value"] if kpi_row is not None else row["ending_value"]

            table_rows.append({"brand": brand, "value": value})
            combined_rows.append({"brand": brand, "kpi": metric, "value": value})

        per_metric_tables[metric] = table_rows

    return per_metric_tables, combined_rows


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def run_brand_comparisons() -> dict:
    kpi_rows = _read_csv(MARKET_KPIS_CSV)
    trend_rows = _read_csv(METRIC_TRENDS_CSV)

    per_metric_tables, combined_rows = build_brand_comparisons(trend_rows, kpi_rows)

    created_files: list[dict] = []
    for metric, rows in sorted(per_metric_tables.items()):
        path = OUTPUT_DIR / f"brand_{slugify_metric(metric)}_comparison.csv"
        _write_csv(path, ["brand", "value"], rows)
        created_files.append({
            "file": str(path),
            "row_count": len(rows),
            "brands": sorted({r["brand"] for r in rows}),
        })

    _write_csv(COMBINED_CSV, ["brand", "kpi", "value"], combined_rows)
    created_files.append({
        "file": str(COMBINED_CSV),
        "row_count": len(combined_rows),
        "brands": sorted({r["brand"] for r in combined_rows}),
    })

    return {"created_files": created_files}
