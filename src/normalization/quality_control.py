"""
Quality control for Phase 2 observations.

Two layers of QC:

1. Per-observation validation (numeric sanity, percentage range,
   currency retention) - runs at creation time.
2. Cross-observation validation (duplicate detection, conflicting
   values for the same metric/entity/period/geography reported on
   different pages) - runs once the full candidate set for a document
   is assembled, since it requires comparing across pages/tables.

Nothing here silently fixes or drops a bad value; every issue is
recorded via ``needs_review`` + ``review_reason`` so a human can decide.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class ObservationRecord:
    """A fully-resolved, not-yet-persisted candidate observation."""

    document_id: int
    table_id: int
    page_number: int
    table_reference: str
    extraction_method: str

    original_metric_name: str
    metric_id: str

    original_value: str
    standardized_value: float | None
    original_unit: str | None
    standardized_unit: str | None

    entity_name: str | None
    entity_type: str | None
    entity_match_confidence: float
    entity_match_method: str

    geography: str | None
    period_label: str | None
    period_year: int | None
    period_quarter: int | None
    period_type: str | None

    extraction_confidence: float
    classification_confidence: float
    table_relevance_score: float

    needs_review: bool = False
    review_reasons: list[str] = field(default_factory=list)

    @property
    def evidence_grade(self) -> str:
        if self.extraction_confidence >= 0.8 and self.classification_confidence >= 0.7 and not self.needs_review:
            return "A"
        if self.extraction_confidence >= 0.5 and self.classification_confidence >= 0.4:
            return "B"
        return "C"

    def flag(self, reason: str) -> None:
        self.needs_review = True
        self.review_reasons.append(reason)


def validate_observation(obs: ObservationRecord) -> None:
    """Per-observation sanity checks. Mutates obs in place via .flag()."""
    if obs.standardized_value is None:
        obs.flag("Value could not be parsed to a number")
        return

    if obs.standardized_unit == "%":
        if not (0 <= obs.standardized_value <= 100):
            # CAGR/growth figures can occasionally exceed 100% legitimately,
            # so this is a review flag, not a hard rejection.
            obs.flag(f"Percentage value {obs.standardized_value} is outside the typical 0-100 range")

    if obs.original_unit is None and obs.standardized_unit is None and obs.metric_id not in ("number_of_centers", "number_of_cities", "number_of_clients"):
        obs.flag("No unit could be determined for a metric that normally has one")

    if obs.entity_match_method == "unresolved":
        obs.flag("Entity could not be confidently resolved")

    if obs.period_label is None:
        obs.flag("Reporting period could not be determined from context")

    if obs.extraction_confidence < 0.6:
        obs.flag(f"Low extraction confidence ({obs.extraction_confidence})")

    if obs.classification_confidence < 0.5:
        obs.flag(f"Low table-classification confidence ({obs.classification_confidence})")


@dataclass
class CrossCheckSummary:
    duplicates_detected: int = 0
    conflicts_detected: int = 0


def run_cross_observation_checks(observations: list[ObservationRecord]) -> CrossCheckSummary:
    """
    Group observations by (metric, entity, period, geography) and flag:
    - conflicts: same group, different standardized_value
    - duplicates: same group, same standardized_value, reported more than once
    """
    groups: dict[tuple, list[ObservationRecord]] = defaultdict(list)
    for obs in observations:
        if obs.standardized_value is None:
            continue
        # An unresolved period or entity means "unknown", not "the same
        # unknown" - grouping those together would produce false
        # conflicts/duplicates between genuinely unrelated observations,
        # so only compare observations whose key dimensions are resolved.
        if obs.period_label is None or obs.entity_name is None:
            continue
        key = (obs.metric_id, obs.entity_name, obs.period_label, obs.geography)
        groups[key].append(obs)

    summary = CrossCheckSummary()

    for key, group in groups.items():
        if len(group) < 2:
            continue

        distinct_values = {round(o.standardized_value, 6) for o in group}
        if len(distinct_values) > 1:
            pages = ", ".join(sorted({f"p{o.page_number}" for o in group}))
            for obs in group:
                obs.flag(f"Conflicting value reported across pages ({pages}) for the same metric/entity/period")
            summary.conflicts_detected += 1
        else:
            pages = sorted({o.page_number for o in group})
            for obs in group[1:]:
                obs.flag(f"Duplicate of an observation already recorded from page {pages[0]}")
            summary.duplicates_detected += 1

    return summary
