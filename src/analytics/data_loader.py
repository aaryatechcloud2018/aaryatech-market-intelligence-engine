"""
Phase 4 data loading.

Deliberately reads ONLY from CSVs already produced by Phase 2 (Silver
export) and Phase 3 (review classification) - never opens the SQLite
database. This guarantees Phase 4 cannot accidentally modify Bronze or
Silver data: it is a pure CSV-in, CSV-out analytical layer.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from src.config import SILVER_DIR, SILVER_OBSERVATIONS_DIR

ANALYSIS_READY_CSV = SILVER_DIR / "analysis_ready_observations.csv"
ALL_OBSERVATIONS_CSV = SILVER_OBSERVATIONS_DIR / "fact_observations_all.csv"
PHASE3_QUALITY_SUMMARY_CSV = SILVER_DIR / "data_quality_summary.csv"

_YEAR_RE = re.compile(r"(19|20)\d{2}")


@dataclass
class Observation:
    observation_id: int
    metric_id: str
    metric_name: str
    entity_name: str | None
    entity_type: str | None
    geography: str | None
    value: str  # original as-reported string, never overwritten
    normalized_value: float | None
    unit: str | None
    period: str | None
    period_year: int | None  # derived purely for chronological ordering/pairing
    source_document: str
    page_number: int | None
    table_reference: str | None
    extraction_confidence: float | None
    classification_confidence: float | None
    evidence_grade: str | None


def _to_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _to_int(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def extract_period_year(period_label: str | None) -> int | None:
    """
    Derive a sortable calendar/fiscal year from a period label like
    "FY2025" or "2025". This is used ONLY to order and pair periods
    chronologically - the original period label is always preserved
    alongside it and is what gets reported.
    """
    if not period_label:
        return None
    match = _YEAR_RE.search(period_label)
    return int(match.group()) if match else None


def load_analysis_ready_observations(path: Path = ANALYSIS_READY_CSV) -> list[Observation]:
    """
    Load ONLY the ANALYSIS_READY observations produced by Phase 3. This
    is the sole input for automated KPI/trend/business-performance/
    hypothesis calculations - NEEDS_REVIEW, DUPLICATE, CONFLICT, and
    INSUFFICIENT_CONTEXT records are never read by this function.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found - run scripts/run_phase3_review.py first."
        )

    observations: list[Observation] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("status") != "ANALYSIS_READY":
                # Defensive: the file should already contain only these,
                # but never silently trust an input file's filename alone.
                continue
            observations.append(
                Observation(
                    observation_id=int(row["observation_id"]),
                    metric_id=row["metric_id"],
                    metric_name=row["metric_name"],
                    entity_name=row.get("entity_name") or None,
                    entity_type=row.get("entity_type") or None,
                    geography=row.get("geography") or None,
                    value=row["value"],
                    normalized_value=_to_float(row.get("normalized_value")),
                    unit=row.get("unit") or None,
                    period=row.get("period") or None,
                    period_year=extract_period_year(row.get("period")),
                    source_document=row["source_document"],
                    page_number=_to_int(row.get("page_number")),
                    table_reference=row.get("table_reference") or None,
                    extraction_confidence=_to_float(row.get("extraction_confidence")),
                    classification_confidence=_to_float(row.get("classification_confidence")),
                    evidence_grade=row.get("evidence_grade") or None,
                )
            )
    return observations


def load_phase3_quality_summary(path: Path = PHASE3_QUALITY_SUMMARY_CSV) -> dict[str, str]:
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {row["metric"]: row["value"] for row in csv.DictReader(f)}


def load_all_observations_pages_and_documents(path: Path = ALL_OBSERVATIONS_CSV) -> tuple[set[int], set[str]]:
    """Distinct page numbers and source documents across the FULL Silver observation set (all 417)."""
    if not path.exists():
        return set(), set()
    pages: set[int] = set()
    documents: set[str] = set()
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            page = _to_int(row.get("page_number"))
            if page is not None:
                pages.add(page)
            doc = row.get("source_document")
            if doc:
                documents.add(doc)
    return pages, documents
