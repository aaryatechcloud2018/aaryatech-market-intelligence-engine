"""
Phase 3: low-confidence data recovery and analysis-ready export.

This is deliberately thin: it reads the existing Silver-layer
fact_observation rows (produced by Phase 2) and computes three things
purely in memory, at export time - nothing is written back to
fact_observation, so the original Silver data is never modified:

1. A review ``status`` (ANALYSIS_READY / NEEDS_REVIEW / DUPLICATE /
   CONFLICT / INSUFFICIENT_CONTEXT), derived from the existing
   ``needs_review`` flag and ``review_reason`` text that Phase 2's
   quality control already recorded.
2. A human-friendly ``candidate_metric_name``, derived from the
   existing metric_id -> dim_metric.display_name lookup (already
   resolved by Phase 2's keyword-based extraction), with a
   "Competitor " prefix when the observation is attributed to a
   competitor entity. Falls back to UNKNOWN_METRIC only if an
   observation somehow has no metric_id at all.
3. A simple review ``priority`` (P1/P2/P3), from a small fixed lookup
   table - not a scoring model.

No new database tables or columns are introduced.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from src.config import SILVER_DIR
from src.db.init_db import initialize_database
from src.db.schema import DimDate, DimDocument, DimEntity, DimGeography, DimMetric, FactObservation
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

STATUS_ANALYSIS_READY = "ANALYSIS_READY"
STATUS_NEEDS_REVIEW = "NEEDS_REVIEW"
STATUS_DUPLICATE = "DUPLICATE"
STATUS_CONFLICT = "CONFLICT"
STATUS_INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"

_REVIEW_STATUSES = (STATUS_NEEDS_REVIEW, STATUS_DUPLICATE, STATUS_CONFLICT, STATUS_INSUFFICIENT_CONTEXT)

# Substrings of review_reason (as written by Phase 2's quality_control.py)
# that indicate the observation is missing context needed to place it,
# rather than just carrying a generic low-confidence score.
_INSUFFICIENT_CONTEXT_SIGNALS = (
    "period could not be determined",
    "entity could not be confidently resolved",
    "no unit could be determined",
    "value could not be parsed",
)

# --- Priority lookup (Step 6) - a small fixed table, not a scoring model ---
_P1_METRIC_IDS = {
    "total_revenue", "ebitda", "adjusted_ebitda", "ebitda_margin", "profit_margin",
    "net_profit", "number_of_centers", "total_seating_capacity", "chargeable_seats",
    "occupancy_rate",
}
_P2_METRIC_IDS = {
    "market_size", "market_growth_rate", "market_share", "price_per_seat",
    "number_of_clients", "client_concentration_top10", "number_of_cities",
    "area_under_management",
}


def classify_status(needs_review: bool, review_reason: str | None) -> str:
    """Map Phase 2's existing needs_review/review_reason onto one of the 5 Phase 3 statuses."""
    if not needs_review:
        return STATUS_ANALYSIS_READY

    reason = (review_reason or "").lower()

    if "conflicting value" in reason:
        return STATUS_CONFLICT
    if "duplicate of" in reason:
        return STATUS_DUPLICATE
    if any(signal in reason for signal in _INSUFFICIENT_CONTEXT_SIGNALS):
        return STATUS_INSUFFICIENT_CONTEXT
    return STATUS_NEEDS_REVIEW


def candidate_metric_name(metric_display_name: str | None, entity_type: str | None) -> str:
    """A meaningful, human-readable metric name - never invented if the metric is unknown."""
    if not metric_display_name:
        return "UNKNOWN_METRIC"
    if entity_type == "COMPETITOR":
        return f"Competitor {metric_display_name}"
    return metric_display_name


def assign_priority(metric_id: str | None, entity_type: str | None) -> str:
    """Simple fixed P1/P2/P3 lookup - not a scoring system."""
    if entity_type == "COMPETITOR":
        return "P2"
    if metric_id in _P1_METRIC_IDS:
        return "P1"
    if metric_id in _P2_METRIC_IDS:
        return "P2"
    return "P3"


# ===========================================================================
# Data assembly
# ===========================================================================


def _load_enriched_observations(session: Session, document_id: int | None = None) -> list[dict]:
    """
    Pull every fact_observation row (optionally scoped to one document)
    with its dimension lookups, plus the Phase 3 derived fields. Read-only
    - nothing here writes back to the database.
    """
    query = (
        session.query(FactObservation, DimMetric, DimEntity, DimGeography, DimDate, DimDocument)
        .join(DimMetric, DimMetric.metric_id == FactObservation.metric_id, isouter=True)
        .join(DimEntity, DimEntity.entity_id == FactObservation.entity_id, isouter=True)
        .join(DimGeography, DimGeography.geography_id == FactObservation.geography_id, isouter=True)
        .join(DimDate, DimDate.date_id == FactObservation.date_id, isouter=True)
        .join(DimDocument, DimDocument.document_id == FactObservation.document_id)
    )
    if document_id is not None:
        query = query.filter(FactObservation.document_id == document_id)

    rows = query.order_by(FactObservation.observation_id).all()

    enriched = []
    for obs, metric, entity, geo, date, doc in rows:
        entity_type = entity.entity_type if entity else None
        status = classify_status(obs.needs_review, obs.review_reason)
        metric_name = candidate_metric_name(metric.display_name if metric else None, entity_type)
        priority = assign_priority(obs.metric_id, entity_type)

        enriched.append(
            {
                "observation_id": obs.observation_id,
                "metric_id": obs.metric_id,
                "metric_name": metric_name,
                "entity_name": entity.standardized_name if entity else None,
                "entity_type": entity_type,
                "geography": geo.standardized_name if geo else None,
                "value": obs.original_value,
                "normalized_value": obs.standardized_value,
                "unit": obs.standardized_unit,
                "period": date.period_label if date else obs.period_label_raw,
                "source_document": doc.file_name,
                "page_number": obs.page_number,
                "table_reference": obs.table_reference,
                "extraction_confidence": obs.confidence,
                "classification_confidence": obs.classification_confidence,
                "evidence_grade": obs.evidence_grade,
                "extraction_method": obs.extraction_method,
                "needs_review": obs.needs_review,
                "review_reason": obs.review_reason,
                "status": status,
                "priority": priority,
            }
        )
    return enriched


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fieldnames})


# ===========================================================================
# Exports (Steps 2, 4, 5, 7)
# ===========================================================================

_REVIEW_FIELDNAMES = [
    "observation_id", "metric_name", "entity_name", "entity_type", "geography",
    "value", "unit", "period", "source_document", "page_number", "table_reference",
    "extraction_confidence", "classification_confidence", "status", "priority", "review_reason",
]

_ANALYSIS_READY_FIELDNAMES = [
    "observation_id", "metric_id", "metric_name", "entity_name", "entity_type",
    "value", "normalized_value", "unit", "period", "geography", "source_document",
    "page_number", "table_reference", "extraction_confidence", "classification_confidence",
    "evidence_grade", "extraction_method", "status",
]

_METRIC_SUMMARY_FIELDNAMES = [
    "metric_name", "observation_count", "unique_entities", "unique_periods",
    "average_confidence", "source_pages", "review_status",
]

_QUALITY_SUMMARY_FIELDNAMES = ["metric", "value"]


def export_analysis_ready(observations: list[dict]) -> Path:
    rows = [o for o in observations if o["status"] == STATUS_ANALYSIS_READY]
    path = SILVER_DIR / "analysis_ready_observations.csv"
    _write_csv(path, _ANALYSIS_READY_FIELDNAMES, rows)
    return path


def export_low_confidence_review(observations: list[dict]) -> Path:
    rows = [o for o in observations if o["status"] in _REVIEW_STATUSES]
    path = SILVER_DIR / "low_confidence_review.csv"
    _write_csv(path, _REVIEW_FIELDNAMES, rows)
    return path


def export_low_confidence_metric_summary(observations: list[dict]) -> Path:
    review_rows = [o for o in observations if o["status"] in _REVIEW_STATUSES]

    groups: dict[str, list[dict]] = defaultdict(list)
    for row in review_rows:
        groups[row["metric_name"]].append(row)

    summary_rows = []
    for metric_name, group in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        confidences = [g["extraction_confidence"] for g in group if g["extraction_confidence"] is not None]
        pages = sorted({g["page_number"] for g in group if g["page_number"] is not None})
        statuses = sorted({g["status"] for g in group})
        summary_rows.append(
            {
                "metric_name": metric_name,
                "observation_count": len(group),
                "unique_entities": len({g["entity_name"] for g in group if g["entity_name"]}),
                "unique_periods": len({g["period"] for g in group if g["period"]}),
                "average_confidence": round(sum(confidences) / len(confidences), 3) if confidences else None,
                "source_pages": ";".join(str(p) for p in pages),
                "review_status": ";".join(statuses),
            }
        )

    path = SILVER_DIR / "low_confidence_metric_summary.csv"
    _write_csv(path, _METRIC_SUMMARY_FIELDNAMES, summary_rows)
    return path


def export_data_quality_summary(observations: list[dict]) -> tuple[Path, dict]:
    total = len(observations)
    by_status = {s: sum(1 for o in observations if o["status"] == s) for s in
                 (STATUS_ANALYSIS_READY, STATUS_NEEDS_REVIEW, STATUS_DUPLICATE, STATUS_CONFLICT, STATUS_INSUFFICIENT_CONTEXT)}
    by_grade = {g: sum(1 for o in observations if o["evidence_grade"] == g) for g in ("A", "B", "C")}

    summary = {
        "total_observations": total,
        "analysis_ready": by_status[STATUS_ANALYSIS_READY],
        "needs_review": by_status[STATUS_NEEDS_REVIEW],
        "duplicates": by_status[STATUS_DUPLICATE],
        "conflicts": by_status[STATUS_CONFLICT],
        "insufficient_context": by_status[STATUS_INSUFFICIENT_CONTEXT],
        "high_confidence": by_grade["A"],
        "medium_confidence": by_grade["B"],
        "low_confidence": by_grade["C"],
    }

    rows = [{"metric": k, "value": v} for k, v in summary.items()]
    path = SILVER_DIR / "data_quality_summary.csv"
    _write_csv(path, _QUALITY_SUMMARY_FIELDNAMES, rows)
    return path, summary


# ===========================================================================
# Entry point
# ===========================================================================


def run_phase3_review() -> dict:
    engine = initialize_database()
    session_factory = sessionmaker(bind=engine)

    with session_factory() as session:
        observations = _load_enriched_observations(session)

        if not observations:
            logger.warning("No Silver-layer observations found. Run Phase 2 first.")
            return {}

        analysis_ready_path = export_analysis_ready(observations)
        review_path = export_low_confidence_review(observations)
        metric_summary_path = export_low_confidence_metric_summary(observations)
        quality_summary_path, quality_summary = export_data_quality_summary(observations)

    named_metrics = {o["metric_name"] for o in observations if o["metric_name"] != "UNKNOWN_METRIC"}
    unknown_count = sum(1 for o in observations if o["metric_name"] == "UNKNOWN_METRIC")

    review_rows = [o for o in observations if o["status"] in _REVIEW_STATUSES]
    priority_counts = {p: sum(1 for o in review_rows if o["priority"] == p) for p in ("P1", "P2", "P3")}

    metric_counter: dict[str, int] = defaultdict(int)
    for o in review_rows:
        metric_counter[o["metric_name"]] += 1
    top_low_confidence_metrics = sorted(metric_counter.items(), key=lambda kv: -kv[1])[:20]

    return {
        "total_observations": len(observations),
        "quality_summary": quality_summary,
        "named_metrics": len(named_metrics),
        "unknown_metric_count": unknown_count,
        "top_low_confidence_metrics": top_low_confidence_metrics,
        "priority_counts": priority_counts,
        "output_files": {
            "analysis_ready_observations": str(analysis_ready_path),
            "low_confidence_review": str(review_path),
            "low_confidence_metric_summary": str(metric_summary_path),
            "data_quality_summary": str(quality_summary_path),
        },
    }
