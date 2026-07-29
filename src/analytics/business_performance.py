"""
Simple financial / business performance table (Phase 4, Step 4).

Pivots the analysis-ready observations into one row per (entity, year),
with a fixed set of business-metric columns. Any metric not reported
for a given entity/year is left blank (NULL) - never fabricated or
interpolated. The single derived column, revenue_growth, is only
populated when both a prior-year and current-year revenue value exist
for the same entity (mathematically valid); since this dataset happens
to contain no ANALYSIS_READY revenue observations at all, that column
is expected to be entirely blank for this document - itself a
meaningful, honestly-reported fact about the data.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, fields

from src.analytics.data_loader import Observation
from src.analytics.trend_analysis import safe_percentage_change

# metric_id -> business_performance column name
_COLUMN_METRIC_MAP = {
    "total_revenue": "revenue",
    "ebitda": "EBITDA",
    "ebitda_margin": "EBITDA_margin",
    "net_profit": "net_profit",
    "number_of_centers": "number_of_centers",
    "number_of_clients": "number_of_clients",
    "occupancy_rate": "occupancy_rate",
    "total_assets": "total_assets",
    "total_borrowings": "total_borrowings",
    "net_worth": "net_worth",
}

_METRIC_COLUMNS = list(_COLUMN_METRIC_MAP.values())


@dataclass
class BusinessPerformanceRow:
    entity_name: str
    period: str  # the normalized year used to align this row (e.g. "2025")
    revenue: float | None = None
    revenue_growth: float | None = None
    EBITDA: float | None = None
    EBITDA_margin: float | None = None
    net_profit: float | None = None
    number_of_centers: float | None = None
    number_of_clients: float | None = None
    occupancy_rate: float | None = None
    total_assets: float | None = None
    total_borrowings: float | None = None
    net_worth: float | None = None


def build_business_performance_table(observations: list[Observation]) -> list[BusinessPerformanceRow]:
    # (entity, year) -> {column: best observation for that column}
    cells: dict[tuple[str, int], dict[str, Observation]] = defaultdict(dict)

    for obs in observations:
        column = _COLUMN_METRIC_MAP.get(obs.metric_id)
        if column is None or obs.entity_name is None or obs.period_year is None or obs.normalized_value is None:
            continue
        key = (obs.entity_name, obs.period_year)
        existing = cells[key].get(column)
        if existing is None or (obs.extraction_confidence or 0) > (existing.extraction_confidence or 0):
            cells[key][column] = obs

    rows: list[BusinessPerformanceRow] = []
    for (entity_name, year), columns in sorted(cells.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        row = BusinessPerformanceRow(entity_name=entity_name, period=str(year))
        for column, obs in columns.items():
            setattr(row, column, obs.normalized_value)
        rows.append(row)

    _fill_revenue_growth(rows)
    return rows


def _fill_revenue_growth(rows: list[BusinessPerformanceRow]) -> None:
    by_entity: dict[str, list[BusinessPerformanceRow]] = defaultdict(list)
    for row in rows:
        by_entity[row.entity_name].append(row)

    for entity_rows in by_entity.values():
        entity_rows.sort(key=lambda r: int(r.period))
        for prev, curr in zip(entity_rows, entity_rows[1:]):
            if prev.revenue is not None and curr.revenue is not None:
                curr.revenue_growth = safe_percentage_change(prev.revenue, curr.revenue)


def business_performance_fieldnames() -> list[str]:
    return [f.name for f in fields(BusinessPerformanceRow)]
