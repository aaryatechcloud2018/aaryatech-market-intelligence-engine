"""
Simple KPI analysis (Phase 4, Step 2).

Every ANALYSIS_READY observation is itself a KPI data point (its
metric was already identified and normalized in Phase 2/3) - this
module does not re-derive raw KPI values, it only assembles them into
the market_kpis.csv shape and, where mathematically valid, adds
derived "growth" KPI rows on top.

Growth KPIs are only computed for metrics whose unit is NOT a
percentage: the "growth of a margin/rate" (e.g. growth of an EBITDA
margin already expressed in %) is a different, more ambiguous
statistic (percentage-point change vs. percentage change of a
percentage) and is deliberately left to the existing metric_trends.csv
output instead of being forced into a KPI row here.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.analytics.data_loader import Observation
from src.analytics.trend_analysis import TrendResult, compute_metric_trends


@dataclass
class KpiRow:
    kpi_name: str
    entity: str
    period: str
    value: str  # original as-reported value, never overwritten
    unit: str | None
    source_observation_id: int
    source_document: str
    page_number: int | None
    confidence: float | None


def build_market_kpis(observations: list[Observation]) -> list[KpiRow]:
    rows: list[KpiRow] = []

    for obs in observations:
        if obs.entity_name is None:
            continue  # cannot attribute a KPI to no entity
        rows.append(
            KpiRow(
                kpi_name=obs.metric_name,
                entity=obs.entity_name,
                period=obs.period or "",
                value=obs.value,
                unit=obs.unit,
                source_observation_id=obs.observation_id,
                source_document=obs.source_document,
                page_number=obs.page_number,
                confidence=obs.extraction_confidence,
            )
        )

    for trend in compute_metric_trends(observations):
        if trend.unit == "%":
            continue  # growth-of-a-percentage is not a well-defined KPI here
        if trend.percentage_change is None:
            continue  # e.g. starting value of 0 - growth is undefined, not fabricated
        # Growth is reported "as of" the ending period, so the ending
        # observation is the more relevant single provenance pointer;
        # metric_trends.csv retains both start and end observation IDs.
        end_observation_id = trend.source_observation_ids[-1]
        end_page = max(trend.source_pages) if trend.source_pages else None
        rows.append(
            KpiRow(
                kpi_name=f"{trend.metric_name} Growth",
                entity=trend.entity_name,
                period=f"{trend.period_start} to {trend.period_end}",
                value=f"{trend.percentage_change}%",
                unit="%",
                source_observation_id=end_observation_id,
                source_document=trend.source_document,
                page_number=end_page,
                confidence=None,  # derived value; see analytics_catalog.csv for calculation method
            )
        )

    return rows
