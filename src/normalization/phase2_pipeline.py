"""
Phase 2 pipeline: BRONZE -> table classification -> relevance scoring ->
metric extraction -> normalization -> entity resolution -> provenance ->
SILVER master database.

This module deliberately does NOT summarize the document, generate
insights/market gaps, or run hypothesis tests - it only converts raw
Bronze tables into structured, traceable Silver-layer observations.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from src.config import SILVER_OBSERVATIONS_DIR, SILVER_REPORTS_DIR
from src.db.init_db import initialize_database
from src.db.schema import (
    DimCompany,
    DimCompetitor,
    DimDate,
    DimDocument,
    DimEntity,
    DimGeography,
    DimMetric,
    FactDocumentText,
    FactExtractedTable,
    FactObservation,
)
from src.normalization.entity_resolver import resolve_entity
from src.normalization.metric_definitions import METRIC_DEFINITIONS
from src.normalization.metric_extractor import extract_observations
from src.normalization.quality_control import (
    ObservationRecord,
    run_cross_observation_checks,
    validate_observation,
)
from src.normalization.table_classifier import classify_table
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

RELEVANCE_SKIP_CATEGORY = "IRRELEVANT"

_COMPANY_NAME_RE = re.compile(r"\b([A-Z][A-Z&.,'\- ]{4,80}? LIMITED)\b")


# ===========================================================================
# Setup / seeding
# ===========================================================================


def seed_metric_registry(session: Session) -> None:
    """Ensure every metric in the keyword registry has a dim_metric row."""
    existing_ids = {m.metric_id for m in session.query(DimMetric.metric_id).all()}
    for definition in METRIC_DEFINITIONS:
        if definition.metric_id in existing_ids:
            continue
        session.add(
            DimMetric(
                metric_id=definition.metric_id,
                metric_name=definition.metric_name,
                display_name=definition.display_name,
                description=definition.description,
                category=definition.category,
                unit=definition.unit,
                data_type=definition.data_type,
                source_type="extracted",
                derived_flag=False,
                formula=None,
                aggregation_method=definition.aggregation_method,
            )
        )
    session.commit()


def _detect_document_subject_company(session: Session, document_id: int) -> str | None:
    """
    Look for an ALL-CAPS "... LIMITED" company name in the first few pages
    of the document's extracted text. Returns None (never a guess) if no
    such pattern is found.
    """
    pages = (
        session.query(FactDocumentText)
        .filter(FactDocumentText.document_id == document_id, FactDocumentText.page_number <= 3)
        .order_by(FactDocumentText.page_number)
        .all()
    )
    for page in pages:
        if not page.text_content:
            continue
        match = _COMPANY_NAME_RE.search(page.text_content)
        if match:
            name = re.sub(r"\s+", " ", match.group(1)).strip()
            return name.title()
    return None


# ===========================================================================
# Dimension find-or-create helpers
# ===========================================================================


def _get_or_create_entity(
    session: Session, cache: dict, entity_type: str, name: str, confidence: float, method: str
) -> DimEntity:
    key = (entity_type, name.lower())
    if key in cache:
        return cache[key]
    existing = (
        session.query(DimEntity)
        .filter(DimEntity.entity_type == entity_type, DimEntity.standardized_name == name)
        .one_or_none()
    )
    if existing:
        cache[key] = existing
        return existing
    entity = DimEntity(
        raw_name=name, standardized_name=name, entity_type=entity_type,
        match_confidence=confidence, match_method=method, needs_review=confidence < 0.6,
    )
    session.add(entity)
    session.flush()
    cache[key] = entity
    return entity


def _get_or_create_company(session: Session, cache: dict, name: str) -> DimCompany:
    key = name.lower()
    if key in cache:
        return cache[key]
    existing = session.query(DimCompany).filter(DimCompany.standardized_name == name).one_or_none()
    if existing:
        cache[key] = existing
        return existing
    company = DimCompany(raw_name=name, standardized_name=name)
    session.add(company)
    session.flush()
    cache[key] = company
    return company


def _get_or_create_competitor(session: Session, cache: dict, name: str) -> DimCompetitor:
    key = name.lower()
    if key in cache:
        return cache[key]
    existing = session.query(DimCompetitor).filter(DimCompetitor.standardized_name == name).one_or_none()
    if existing:
        cache[key] = existing
        return existing
    competitor = DimCompetitor(raw_name=name, standardized_name=name)
    session.add(competitor)
    session.flush()
    cache[key] = competitor
    return competitor


def _get_or_create_geography(session: Session, cache: dict, name: str) -> DimGeography:
    key = name.lower()
    if key in cache:
        return cache[key]
    existing = session.query(DimGeography).filter(DimGeography.standardized_name == name).one_or_none()
    if existing:
        cache[key] = existing
        return existing
    geo = DimGeography(raw_name=name, standardized_name=name, geography_level="city", country="India")
    session.add(geo)
    session.flush()
    cache[key] = geo
    return geo


def _get_or_create_date(session: Session, cache: dict, period_label: str, year: int, quarter: int | None, period_type: str) -> DimDate:
    key = (period_label, year, quarter, period_type)
    if key in cache:
        return cache[key]
    existing = (
        session.query(DimDate)
        .filter(DimDate.period_label == period_label, DimDate.year == year, DimDate.period_type == period_type)
        .one_or_none()
    )
    if existing:
        cache[key] = existing
        return existing
    date_row = DimDate(full_date=None, year=year, quarter=quarter, month=None, month_name=None,
                        period_type=period_type, period_label=period_label)
    session.add(date_row)
    session.flush()
    cache[key] = date_row
    return date_row


# ===========================================================================
# Core per-document processing
# ===========================================================================


def process_document_phase2(session: Session, document: DimDocument) -> dict:
    logger.info("Phase 2: processing document_id=%s (%s)", document.document_id, document.file_name)

    bronze_tables = (
        session.query(FactExtractedTable)
        .filter(FactExtractedTable.document_id == document.document_id)
        .order_by(FactExtractedTable.page_number)
        .all()
    )

    document_subject_name = _detect_document_subject_company(session, document.document_id)
    logger.info("Detected document subject company: %s", document_subject_name or "(none found)")

    category_counts: dict[str, int] = {}
    tables_classified = 0
    tables_relevant = 0
    tables_irrelevant = 0

    all_records: list[ObservationRecord] = []

    for table in bronze_tables:
        try:
            rows = json.loads(table.table_data_json) if table.table_data_json else []
        except json.JSONDecodeError:
            rows = []

        result = classify_table(rows)
        table.table_category = result.category
        table.relevance_score = result.relevance_score
        table.classification_confidence = result.confidence
        table.classification_basis = result.basis
        tables_classified += 1
        category_counts[result.category] = category_counts.get(result.category, 0) + 1

        if result.category == RELEVANCE_SKIP_CATEGORY:
            tables_irrelevant += 1
            continue
        tables_relevant += 1

        candidates = extract_observations(rows)
        for cand in candidates:
            resolved = resolve_entity(result.category, cand.row_label, cand.column_header, document_subject_name)

            # Extraction confidence blends: the bronze table's own cell-fill
            # confidence (how trustworthy the raw table extraction was) with
            # this specific value's parse confidence.
            bronze_confidence = table.confidence if table.confidence is not None else 0.5
            extraction_confidence = round((bronze_confidence + cand.parsed_value.parse_confidence) / 2, 3)

            record = ObservationRecord(
                document_id=document.document_id,
                table_id=table.table_id,
                page_number=table.page_number,
                table_reference=table.table_reference,
                extraction_method=f"{table.extraction_method}+rule_based_metric_extraction",
                original_metric_name=cand.row_label,
                metric_id=cand.metric.metric_id,
                original_value=cand.raw_value,
                standardized_value=cand.parsed_value.standardized_value,
                original_unit=cand.column_header,
                standardized_unit=cand.parsed_value.standardized_unit,
                entity_name=resolved.entity_name,
                entity_type=resolved.entity_type,
                entity_match_confidence=resolved.confidence,
                entity_match_method=resolved.match_method,
                geography=cand.geography,
                period_label=cand.parsed_period.period_label if cand.parsed_period else None,
                period_year=cand.parsed_period.year if cand.parsed_period else None,
                period_quarter=cand.parsed_period.quarter if cand.parsed_period else None,
                period_type=cand.parsed_period.period_type if cand.parsed_period else None,
                extraction_confidence=extraction_confidence,
                classification_confidence=result.confidence,
                table_relevance_score=result.relevance_score,
            )
            validate_observation(record)
            all_records.append(record)

    cross_check = run_cross_observation_checks(all_records)

    # --- persist ---
    entity_cache: dict = {}
    company_cache: dict = {}
    competitor_cache: dict = {}
    geography_cache: dict = {}
    date_cache: dict = {}

    for record in all_records:
        entity_id = None
        company_id = None
        competitor_id = None
        if record.entity_name and record.entity_type:
            entity_row = _get_or_create_entity(
                session, entity_cache, record.entity_type, record.entity_name,
                record.entity_match_confidence, record.entity_match_method,
            )
            entity_id = entity_row.entity_id
            if record.entity_type == "COMPANY":
                company_id = _get_or_create_company(session, company_cache, record.entity_name).company_id
            elif record.entity_type == "COMPETITOR":
                competitor_id = _get_or_create_competitor(session, competitor_cache, record.entity_name).competitor_id

        geography_id = None
        if record.geography:
            geography_id = _get_or_create_geography(session, geography_cache, record.geography).geography_id

        date_id = None
        if record.period_label:
            date_id = _get_or_create_date(
                session, date_cache, record.period_label, record.period_year,
                record.period_quarter, record.period_type,
            ).date_id

        session.add(
            FactObservation(
                document_id=record.document_id,
                table_id=record.table_id,
                page_number=record.page_number,
                table_reference=record.table_reference,
                extraction_method=record.extraction_method,
                original_metric_name=record.original_metric_name,
                metric_id=record.metric_id,
                original_value=record.original_value,
                standardized_value=record.standardized_value,
                original_unit=record.original_unit,
                standardized_unit=record.standardized_unit,
                entity_id=entity_id,
                company_id=company_id,
                competitor_id=competitor_id,
                geography_id=geography_id,
                date_id=date_id,
                period_label_raw=record.period_label,
                confidence=record.extraction_confidence,
                classification_confidence=record.classification_confidence,
                evidence_grade=record.evidence_grade,
                needs_review=record.needs_review,
                review_reason="; ".join(record.review_reasons) if record.review_reasons else None,
            )
        )

    session.commit()

    high_confidence = sum(1 for r in all_records if not r.needs_review)
    low_confidence = sum(1 for r in all_records if r.needs_review)

    return {
        "document_id": document.document_id,
        "file_name": document.file_name,
        "document_subject_company": document_subject_name,
        "tables_total": len(bronze_tables),
        "tables_classified": tables_classified,
        "tables_relevant": tables_relevant,
        "tables_irrelevant": tables_irrelevant,
        "category_counts": category_counts,
        "observations_created": len(all_records),
        "high_confidence_observations": high_confidence,
        "low_confidence_observations": low_confidence,
        "duplicates_detected": cross_check.duplicates_detected,
        "conflicts_detected": cross_check.conflicts_detected,
        "unique_entities": len({(r.entity_type, r.entity_name) for r in all_records if r.entity_name}),
        "unique_metrics": len({r.metric_id for r in all_records}),
        "unique_geographies": len({r.geography for r in all_records if r.geography}),
    }


# ===========================================================================
# Outputs
# ===========================================================================


def _observation_rows_for_export(session: Session, document_id: int) -> list[dict]:
    rows = (
        session.query(FactObservation, DimMetric, DimEntity, DimGeography, DimDate, DimDocument)
        .join(DimMetric, DimMetric.metric_id == FactObservation.metric_id, isouter=True)
        .join(DimEntity, DimEntity.entity_id == FactObservation.entity_id, isouter=True)
        .join(DimGeography, DimGeography.geography_id == FactObservation.geography_id, isouter=True)
        .join(DimDate, DimDate.date_id == FactObservation.date_id, isouter=True)
        .join(DimDocument, DimDocument.document_id == FactObservation.document_id)
        .filter(FactObservation.document_id == document_id)
        .order_by(FactObservation.observation_id)
        .all()
    )

    out = []
    for obs, metric, entity, geo, date, doc in rows:
        out.append(
            {
                "observation_id": obs.observation_id,
                "metric_id": obs.metric_id,
                "metric_name": metric.display_name if metric else obs.original_metric_name,
                "entity_name": entity.standardized_name if entity else None,
                "entity_type": entity.entity_type if entity else None,
                "value": obs.original_value,
                "normalized_value": obs.standardized_value,
                "unit": obs.standardized_unit,
                "period": date.period_label if date else obs.period_label_raw,
                "geography": geo.standardized_name if geo else None,
                "source_document": doc.file_name,
                "page_number": obs.page_number,
                "table_reference": obs.table_reference,
                "extraction_confidence": obs.confidence,
                "classification_confidence": obs.classification_confidence,
                "evidence_grade": obs.evidence_grade,
                "extraction_method": obs.extraction_method,
                "needs_review": obs.needs_review,
                "review_reason": obs.review_reason,
            }
        )
    return out


_OBS_FIELDNAMES = [
    "observation_id", "metric_id", "metric_name", "entity_name", "entity_type",
    "value", "normalized_value", "unit", "period", "geography", "source_document",
    "page_number", "table_reference", "extraction_confidence", "classification_confidence",
    "evidence_grade", "extraction_method", "needs_review", "review_reason",
]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def export_observation_csvs(session: Session, document_id: int) -> dict:
    all_rows = _observation_rows_for_export(session, document_id)
    high_conf_rows = [r for r in all_rows if not r["needs_review"]]
    review_rows = [r for r in all_rows if r["needs_review"]]

    all_path = SILVER_OBSERVATIONS_DIR / "fact_observations_all.csv"
    high_path = SILVER_OBSERVATIONS_DIR / "fact_observations_high_confidence.csv"
    review_path = SILVER_OBSERVATIONS_DIR / "fact_observations_needs_review.csv"

    _write_csv(all_path, _OBS_FIELDNAMES, all_rows)
    _write_csv(high_path, _OBS_FIELDNAMES, high_conf_rows)
    _write_csv(review_path, _OBS_FIELDNAMES, review_rows)

    return {"all": str(all_path), "high_confidence": str(high_path), "needs_review": str(review_path)}


def export_table_classification_report(session: Session, document_id: int) -> str:
    tables = (
        session.query(FactExtractedTable)
        .filter(FactExtractedTable.document_id == document_id)
        .order_by(FactExtractedTable.page_number, FactExtractedTable.table_id)
        .all()
    )
    rows = [
        {
            "table_id": t.table_id,
            "page_number": t.page_number,
            "table_reference": t.table_reference,
            "row_count": t.row_count,
            "column_count": t.column_count,
            "bronze_extraction_status": t.extraction_status,
            "bronze_extraction_confidence": t.confidence,
            "table_category": t.table_category,
            "relevance_score": t.relevance_score,
            "classification_confidence": t.classification_confidence,
            "classification_basis": t.classification_basis,
        }
        for t in tables
    ]
    path = SILVER_REPORTS_DIR / "table_classification_report.csv"
    _write_csv(
        path,
        ["table_id", "page_number", "table_reference", "row_count", "column_count",
         "bronze_extraction_status", "bronze_extraction_confidence", "table_category",
         "relevance_score", "classification_confidence", "classification_basis"],
        rows,
    )
    return str(path)


def export_metric_registry(session: Session) -> str:
    metrics = session.query(DimMetric).order_by(DimMetric.category, DimMetric.metric_id).all()
    rows = [
        {
            "metric_id": m.metric_id, "metric_name": m.metric_name, "display_name": m.display_name,
            "description": m.description, "category": m.category, "unit": m.unit,
            "data_type": m.data_type, "source_type": m.source_type, "derived_flag": m.derived_flag,
            "aggregation_method": m.aggregation_method,
        }
        for m in metrics
    ]
    path = SILVER_REPORTS_DIR / "metric_registry.csv"
    _write_csv(
        path,
        ["metric_id", "metric_name", "display_name", "description", "category", "unit",
         "data_type", "source_type", "derived_flag", "aggregation_method"],
        rows,
    )
    return str(path)


def export_entity_registry(session: Session) -> str:
    entities = session.query(DimEntity).order_by(DimEntity.entity_type, DimEntity.standardized_name).all()
    rows = [
        {
            "entity_id": e.entity_id, "raw_name": e.raw_name, "standardized_name": e.standardized_name,
            "entity_type": e.entity_type, "match_confidence": e.match_confidence,
            "match_method": e.match_method, "needs_review": e.needs_review,
        }
        for e in entities
    ]
    path = SILVER_REPORTS_DIR / "entity_registry.csv"
    _write_csv(
        path,
        ["entity_id", "raw_name", "standardized_name", "entity_type", "match_confidence",
         "match_method", "needs_review"],
        rows,
    )
    return str(path)


def export_data_quality_report(summary: dict) -> str:
    path = SILVER_REPORTS_DIR / "data_quality_report.csv"
    rows = [
        {"metric": k, "value": json.dumps(v) if isinstance(v, dict) else v}
        for k, v in summary.items()
        if k != "output_files"
    ]
    _write_csv(path, ["metric", "value"], rows)
    return str(path)


# ===========================================================================
# Entry point
# ===========================================================================


def run_phase2_normalization() -> list[dict]:
    engine = initialize_database()
    session_factory = sessionmaker(bind=engine)

    results = []
    with session_factory() as session:
        seed_metric_registry(session)

        documents = (
            session.query(DimDocument)
            .filter(DimDocument.extraction_status.in_(["success", "partial"]))
            .all()
        )
        if not documents:
            logger.warning("No successfully-extracted documents found. Run Phase 1 first.")
            return []

        for document in documents:
            summary = process_document_phase2(session, document)
            summary["output_files"] = export_observation_csvs(session, document.document_id)
            summary["output_files"]["table_classification_report"] = export_table_classification_report(
                session, document.document_id
            )
            summary["output_files"]["metric_registry"] = export_metric_registry(session)
            summary["output_files"]["entity_registry"] = export_entity_registry(session)
            summary["output_files"]["data_quality_report"] = export_data_quality_report(summary)
            results.append(summary)

    return results
