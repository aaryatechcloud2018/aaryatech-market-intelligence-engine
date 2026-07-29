"""
Phase 4 pipeline: Silver (analysis-ready observations) -> Gold
(Power BI-ready CSVs).

Pure CSV-in, CSV-out. Never opens the SQLite database, so Bronze/Silver
data and the 417 underlying observations cannot be modified by this
phase - it only reads data/silver/*.csv and writes data/gold/powerbi/*.csv.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, fields
from pathlib import Path

from src.analytics.business_performance import build_business_performance_table, business_performance_fieldnames
from src.analytics.catalog import build_analytics_catalog
from src.analytics.data_loader import (
    load_all_observations_pages_and_documents,
    load_analysis_ready_observations,
    load_phase3_quality_summary,
)
from src.analytics.hypothesis_testing import run_hypothesis_tests
from src.analytics.kpi_builder import build_market_kpis
from src.config import GOLD_POWERBI_DIR
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def run_phase4_analytics() -> dict:
    observations = load_analysis_ready_observations()
    logger.info("Loaded %d ANALYSIS_READY observations", len(observations))

    # --- Step 2: market KPIs ---
    kpi_rows = build_market_kpis(observations)
    kpi_path = GOLD_POWERBI_DIR / "market_kpis.csv"
    _write_csv(
        kpi_path,
        ["kpi_name", "entity", "period", "value", "unit", "source_observation_id",
         "source_document", "page_number", "confidence"],
        [asdict(r) for r in kpi_rows],
    )

    # --- Step 3: trend analysis ---
    from src.analytics.trend_analysis import compute_metric_trends
    trends = compute_metric_trends(observations)
    trends_path = GOLD_POWERBI_DIR / "metric_trends.csv"
    trend_rows = []
    for t in trends:
        d = asdict(t)
        d["source_observation_ids"] = ";".join(str(i) for i in t.source_observation_ids)
        d["source_pages"] = ";".join(str(p) for p in t.source_pages)
        d.pop("metric_id")
        trend_rows.append(d)
    _write_csv(
        trends_path,
        ["metric_name", "entity_name", "entity_type", "unit", "period_start", "period_end",
         "starting_value", "ending_value", "absolute_change", "percentage_change", "trend_direction",
         "source_observation_ids", "source_document", "source_pages"],
        trend_rows,
    )

    # --- Step 4: business performance table ---
    performance_rows = build_business_performance_table(observations)
    performance_path = GOLD_POWERBI_DIR / "business_performance.csv"
    _write_csv(
        performance_path,
        business_performance_fieldnames(),
        [asdict(r) for r in performance_rows],
    )

    # --- Step 5: hypothesis testing ---
    hypothesis_results = run_hypothesis_tests(observations)
    hypothesis_path = GOLD_POWERBI_DIR / "hypothesis_results.csv"
    _write_csv(
        hypothesis_path,
        [f.name for f in fields(hypothesis_results[0])],
        [asdict(r) for r in hypothesis_results],
    )

    # --- Step 6: data quality summary ---
    phase3_summary = load_phase3_quality_summary()
    all_pages, all_documents = load_all_observations_pages_and_documents()
    quality_summary = {
        **phase3_summary,
        "source_pages": ";".join(str(p) for p in sorted(all_pages)),
        "source_documents": ";".join(sorted(all_documents)),
    }
    quality_path = GOLD_POWERBI_DIR / "data_quality_summary.csv"
    _write_csv(
        quality_path,
        ["metric", "value"],
        [{"metric": k, "value": v} for k, v in quality_summary.items()],
    )

    # --- Step 7: analytics catalog ---
    catalog_entries = build_analytics_catalog(kpi_rows)
    catalog_path = GOLD_POWERBI_DIR / "analytics_catalog.csv"
    catalog_rows = []
    for entry in catalog_entries:
        d = asdict(entry)
        d["source_observation_ids"] = ";".join(str(i) for i in entry.source_observation_ids)
        d["source_page"] = ";".join(str(p) for p in entry.source_page)
        catalog_rows.append(d)
    _write_csv(
        catalog_path,
        ["metric_name", "definition", "calculation_method", "unit", "source_observation_ids",
         "source_document", "source_page", "confidence", "analysis_status"],
        catalog_rows,
    )

    valid_hypotheses = sum(1 for h in hypothesis_results if h.result not in ("INSUFFICIENT_DATA",))
    insufficient_hypotheses = sum(1 for h in hypothesis_results if h.result == "INSUFFICIENT_DATA")

    return {
        "analysis_ready_observations_used": len(observations),
        "kpis_generated": len(kpi_rows),
        "valid_trend_analyses": len(trends),
        "hypothesis_tests_attempted": len(hypothesis_results),
        "hypothesis_tests_valid": valid_hypotheses,
        "hypothesis_tests_insufficient": insufficient_hypotheses,
        "main_metrics": sorted({r.kpi_name for r in kpi_rows}),
        "output_files": {
            "market_kpis": str(kpi_path),
            "metric_trends": str(trends_path),
            "business_performance": str(performance_path),
            "hypothesis_results": str(hypothesis_path),
            "data_quality_summary": str(quality_path),
            "analytics_catalog": str(catalog_path),
        },
    }
