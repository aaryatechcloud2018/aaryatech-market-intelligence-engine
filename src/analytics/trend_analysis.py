"""
Basic trend analysis (Phase 4, Step 3).

For a single metric + a single entity, compares the earliest and latest
available period and computes absolute/percentage change and a simple
trend direction. Never compares across different metric definitions or
across different entities - each (metric_id, entity_name) group is
analyzed in isolation.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from src.analytics.data_loader import Observation

# A percentage change smaller than this magnitude is considered noise,
# not a real trend - a simple, documented threshold, not a model.
STABLE_THRESHOLD_PCT = 2.0


@dataclass
class TrendResult:
    metric_id: str
    metric_name: str
    entity_name: str
    entity_type: str | None
    unit: str | None
    period_start: str
    period_end: str
    starting_value: float
    ending_value: float
    absolute_change: float
    percentage_change: float | None
    trend_direction: str  # INCREASING / DECREASING / STABLE / INSUFFICIENT_DATA
    source_observation_ids: list[int]
    source_document: str
    source_pages: list[int]


def safe_percentage_change(start: float | None, end: float | None) -> float | None:
    """Percentage change, safely handling zero/None starting values (never fabricates a value)."""
    if start is None or end is None:
        return None
    if start == 0:
        return None  # undefined (division by zero) - not approximated or guessed
    return round((end - start) / abs(start) * 100, 2)


def classify_trend_direction(absolute_change: float | None, percentage_change: float | None) -> str:
    if absolute_change is None:
        return "INSUFFICIENT_DATA"
    if percentage_change is not None:
        if abs(percentage_change) < STABLE_THRESHOLD_PCT:
            return "STABLE"
        return "INCREASING" if percentage_change > 0 else "DECREASING"
    # percentage_change undefined (e.g. starting value of 0) - fall back to the raw change.
    if absolute_change == 0:
        return "STABLE"
    return "INCREASING" if absolute_change > 0 else "DECREASING"


def _group_by_metric_and_entity(observations: list[Observation]) -> dict[tuple[str, str], list[Observation]]:
    groups: dict[tuple[str, str], list[Observation]] = defaultdict(list)
    for obs in observations:
        if obs.entity_name is None or obs.normalized_value is None or obs.period_year is None:
            continue  # cannot place this observation on a timeline
        groups[(obs.metric_id, obs.entity_name)].append(obs)
    return groups


def compute_metric_trends(observations: list[Observation]) -> list[TrendResult]:
    """
    For every (metric, entity) pair with 2+ distinct, unambiguous years
    available, compute a trend from the earliest to the latest year.

    If a (metric, entity, year) combination has more than one observation
    (e.g. the same year reported under both "2024" and "FY2024" labels
    elsewhere in the source), the one with the highest extraction
    confidence is used for that year and the rest are excluded from the
    trend calculation - never averaged or arbitrarily picked, and never
    silently dropped from the underlying KPI export.
    """
    trends: list[TrendResult] = []

    for (metric_id, entity_name), group in _group_by_metric_and_entity(observations).items():
        by_year: dict[int, list[Observation]] = defaultdict(list)
        for obs in group:
            by_year[obs.period_year].append(obs)

        year_points: dict[int, Observation] = {}
        for year, obs_list in by_year.items():
            best = max(obs_list, key=lambda o: (o.extraction_confidence or 0.0))
            year_points[year] = best

        years = sorted(year_points)
        if len(years) < 2:
            continue  # only one usable period - no trend to compute

        start_year, end_year = years[0], years[-1]
        start_obs, end_obs = year_points[start_year], year_points[end_year]

        absolute_change = round(end_obs.normalized_value - start_obs.normalized_value, 4)
        percentage_change = safe_percentage_change(start_obs.normalized_value, end_obs.normalized_value)
        direction = classify_trend_direction(absolute_change, percentage_change)

        trends.append(
            TrendResult(
                metric_id=metric_id,
                metric_name=start_obs.metric_name,
                entity_name=entity_name,
                entity_type=start_obs.entity_type,
                unit=start_obs.unit,
                period_start=start_obs.period,
                period_end=end_obs.period,
                starting_value=start_obs.normalized_value,
                ending_value=end_obs.normalized_value,
                absolute_change=absolute_change,
                percentage_change=percentage_change,
                trend_direction=direction,
                source_observation_ids=[start_obs.observation_id, end_obs.observation_id],
                source_document=start_obs.source_document,
                source_pages=sorted({start_obs.page_number, end_obs.page_number} - {None}),
            )
        )

    return trends
