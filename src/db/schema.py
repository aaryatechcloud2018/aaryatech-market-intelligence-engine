"""
SQLite database schema for the Aaryatech Market Intelligence Engine.

Design notes
------------
- This schema is intentionally shared across all three future products
  (Market Intelligence, Investment Intelligence, Audience & Growth
  Intelligence). Dimension tables (dim_*) describe "who/what/where/when",
  and fact tables (fact_*) hold measurements and derived analysis, each
  traceable back to a source document.
- ``dim_metric`` is a metric REGISTRY: new KPIs are added as rows, not as
  new columns, so the schema never needs to change when a new metric is
  introduced.
- Every numeric observation in ``fact_observation`` (and the metric fact
  tables derived from it) preserves full provenance: source, document,
  page, table reference, original value/unit, standardized value/unit,
  extraction method, confidence and evidence grade.
- Primary keys are simple integers (SQLite ``INTEGER PRIMARY KEY``)
  except for ``dim_metric``, which uses a human-readable string ID
  (e.g. ``total_flex_stock``) since metric IDs are referenced directly
  in code and in Power BI measures.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def _utcnow() -> dt.datetime:
    return dt.datetime.utcnow()


# ===========================================================================
# DIMENSION / MASTER TABLES
# ===========================================================================


class DimProject(Base):
    """A market-research engagement/project (allows multi-project use)."""

    __tablename__ = "dim_project"

    project_id = Column(Integer, primary_key=True, autoincrement=True)
    project_name = Column(String, nullable=False, unique=True)
    client_name = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    industry_focus = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class DimCompany(Base):
    """The subject company / client company being researched."""

    __tablename__ = "dim_company"

    company_id = Column(Integer, primary_key=True, autoincrement=True)
    raw_name = Column(String, nullable=False)
    standardized_name = Column(String, nullable=False)
    industry = Column(String, nullable=True)
    headquarters_geography_id = Column(
        Integer, ForeignKey("dim_geography.geography_id"), nullable=True
    )
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class DimCompetitor(Base):
    """A competitor entity, optionally linked back to a parent company."""

    __tablename__ = "dim_competitor"

    competitor_id = Column(Integer, primary_key=True, autoincrement=True)
    raw_name = Column(String, nullable=False)
    standardized_name = Column(String, nullable=False)
    parent_company_id = Column(
        Integer, ForeignKey("dim_company.company_id"), nullable=True
    )
    industry = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class DimGeography(Base):
    """Hierarchical geography master (country / state / city / region)."""

    __tablename__ = "dim_geography"

    geography_id = Column(Integer, primary_key=True, autoincrement=True)
    raw_name = Column(String, nullable=False)
    standardized_name = Column(String, nullable=False)
    geography_level = Column(String, nullable=True)  # country/state/city/region
    parent_geography_id = Column(
        Integer, ForeignKey("dim_geography.geography_id"), nullable=True
    )
    country = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class DimDate(Base):
    """Calendar/period master supporting daily through annual granularity."""

    __tablename__ = "dim_date"

    date_id = Column(Integer, primary_key=True, autoincrement=True)
    full_date = Column(String, nullable=True)  # ISO date, nullable for period-only rows (e.g. "Q3 2025")
    year = Column(Integer, nullable=False)
    quarter = Column(Integer, nullable=True)
    month = Column(Integer, nullable=True)
    month_name = Column(String, nullable=True)
    period_type = Column(String, nullable=False)  # daily/monthly/quarterly/annual
    period_label = Column(String, nullable=False)  # e.g. "Q3 2025", "2025", "2025-09"


class DimMetric(Base):
    """
    Metric registry. Adding a new KPI = inserting a new row here, never a
    schema change.
    """

    __tablename__ = "dim_metric"

    metric_id = Column(String, primary_key=True)  # e.g. "total_flex_stock"
    metric_name = Column(String, nullable=False)
    display_name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=True)  # e.g. market_size, pricing, growth
    unit = Column(String, nullable=True)  # standardized unit, e.g. sqft, INR, %
    data_type = Column(String, nullable=False, default="numeric")  # numeric/categorical/text
    source_type = Column(String, nullable=True)  # reported/estimated/derived
    derived_flag = Column(Boolean, nullable=False, default=False)
    formula = Column(Text, nullable=True)  # only set when derived_flag is True
    aggregation_method = Column(String, nullable=True)  # sum/mean/latest/etc.
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class DimSource(Base):
    """A publisher/source organization (e.g. CBRE, government body)."""

    __tablename__ = "dim_source"

    source_id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(String, nullable=False)
    source_type = Column(String, nullable=True)
    # industry_report / company_report / annual_report / competitor_report /
    # government_report / news / other
    publisher = Column(String, nullable=True)
    credibility_tier = Column(String, nullable=True)  # e.g. tier_1/tier_2/unverified
    url = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class DimDocument(Base):
    """Every ingested file, one row per document, regardless of file type."""

    __tablename__ = "dim_document"

    document_id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("dim_source.source_id"), nullable=True)
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # pdf/csv/excel/json/text
    file_hash = Column(String, nullable=True)  # sha256, used for de-duplication
    file_size_bytes = Column(Integer, nullable=True)
    publication_date = Column(String, nullable=True)  # as stated in the doc, if known
    ingestion_timestamp = Column(DateTime, default=_utcnow, nullable=False)
    extraction_status = Column(
        String, nullable=False, default="pending"
    )  # pending/success/partial/failed
    extraction_method = Column(String, nullable=True)  # e.g. pymupdf/pdfplumber/ocr
    page_count = Column(Integer, nullable=True)
    is_scanned = Column(Boolean, nullable=True)
    error_message = Column(Text, nullable=True)


class DimEntity(Base):
    """
    Entity resolution registry: maps raw name variants to a standardized
    entity (company, competitor, geography, or metric name variant).
    """

    __tablename__ = "dim_entity"

    entity_id = Column(Integer, primary_key=True, autoincrement=True)
    raw_name = Column(String, nullable=False)
    standardized_name = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)  # company/competitor/geography/metric
    match_confidence = Column(Float, nullable=True)  # 0.0 - 1.0
    match_method = Column(String, nullable=True)  # exact/fuzzy/manual/llm
    needs_review = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


# ===========================================================================
# FACT / ANALYTICAL TABLES
# ===========================================================================


class FactDocumentText(Base):
    """Raw extracted text, one row per page (Bronze layer)."""

    __tablename__ = "fact_document_text"

    text_id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(
        Integer, ForeignKey("dim_document.document_id"), nullable=False
    )
    page_number = Column(Integer, nullable=True)
    text_content = Column(Text, nullable=True)
    char_count = Column(Integer, nullable=True)
    extraction_method = Column(String, nullable=True)
    extraction_status = Column(String, nullable=False, default="success")
    # success / needs_review / failed
    error_message = Column(Text, nullable=True)
    ingestion_timestamp = Column(DateTime, default=_utcnow, nullable=False)


class FactExtractedTable(Base):
    """Raw extracted tables, stored as JSON (Bronze layer)."""

    __tablename__ = "fact_extracted_table"

    table_id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(
        Integer, ForeignKey("dim_document.document_id"), nullable=False
    )
    page_number = Column(Integer, nullable=True)
    table_reference = Column(String, nullable=True)  # e.g. "Table 3"
    table_data_json = Column(Text, nullable=True)  # serialized list-of-rows
    row_count = Column(Integer, nullable=True)
    column_count = Column(Integer, nullable=True)
    extraction_method = Column(String, nullable=True)
    extraction_status = Column(String, nullable=False, default="success")
    # success / needs_review - flags tables extracted with low confidence
    # (e.g. mostly empty cells) so they are never silently trusted.
    confidence = Column(Float, nullable=True)  # 0.0 - 1.0, fraction of filled cells
    review_reason = Column(Text, nullable=True)
    ingestion_timestamp = Column(DateTime, default=_utcnow, nullable=False)


class FactObservation(Base):
    """
    The central provenance table. Every standardized numeric fact in the
    system traces back to exactly one row here, which preserves both the
    original (as-reported) value and the standardized value together with
    full source/document/page/table lineage.
    """

    __tablename__ = "fact_observation"

    observation_id = Column(Integer, primary_key=True, autoincrement=True)

    # --- provenance ---
    source_id = Column(Integer, ForeignKey("dim_source.source_id"), nullable=True)
    document_id = Column(
        Integer, ForeignKey("dim_document.document_id"), nullable=False
    )
    page_number = Column(Integer, nullable=True)
    table_reference = Column(String, nullable=True)
    extraction_method = Column(String, nullable=True)  # text/table/manual/ocr

    # --- metric ---
    original_metric_name = Column(String, nullable=False)
    metric_id = Column(String, ForeignKey("dim_metric.metric_id"), nullable=True)

    # --- value ---
    original_value = Column(String, nullable=False)  # kept as-reported (string)
    standardized_value = Column(Float, nullable=True)
    original_unit = Column(String, nullable=True)
    standardized_unit = Column(String, nullable=True)

    # --- dimensions ---
    geography_id = Column(Integer, ForeignKey("dim_geography.geography_id"), nullable=True)
    company_id = Column(Integer, ForeignKey("dim_company.company_id"), nullable=True)
    competitor_id = Column(Integer, ForeignKey("dim_competitor.competitor_id"), nullable=True)
    date_id = Column(Integer, ForeignKey("dim_date.date_id"), nullable=True)
    period_label_raw = Column(String, nullable=True)  # as-reported period text

    # --- quality ---
    confidence = Column(Float, nullable=True)  # 0.0 - 1.0
    evidence_grade = Column(String, nullable=True)  # A/B/C or high/medium/low
    needs_review = Column(Boolean, nullable=False, default=False)

    ingestion_timestamp = Column(DateTime, default=_utcnow, nullable=False)


class FactCompanyMetric(Base):
    """Gold-layer, analysis-ready metrics attributed to the subject company."""

    __tablename__ = "fact_company_metric"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("dim_company.company_id"), nullable=False)
    metric_id = Column(String, ForeignKey("dim_metric.metric_id"), nullable=False)
    date_id = Column(Integer, ForeignKey("dim_date.date_id"), nullable=True)
    geography_id = Column(Integer, ForeignKey("dim_geography.geography_id"), nullable=True)
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=True)
    observation_id = Column(
        Integer, ForeignKey("fact_observation.observation_id"), nullable=True
    )
    confidence = Column(Float, nullable=True)
    ingestion_timestamp = Column(DateTime, default=_utcnow, nullable=False)


class FactMarketMetric(Base):
    """Gold-layer, analysis-ready market-level metrics."""

    __tablename__ = "fact_market_metric"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_id = Column(String, ForeignKey("dim_metric.metric_id"), nullable=False)
    date_id = Column(Integer, ForeignKey("dim_date.date_id"), nullable=True)
    geography_id = Column(Integer, ForeignKey("dim_geography.geography_id"), nullable=True)
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=True)
    observation_id = Column(
        Integer, ForeignKey("fact_observation.observation_id"), nullable=True
    )
    confidence = Column(Float, nullable=True)
    ingestion_timestamp = Column(DateTime, default=_utcnow, nullable=False)


class FactCompetitorMetric(Base):
    """Gold-layer, analysis-ready metrics attributed to a competitor."""

    __tablename__ = "fact_competitor_metric"

    id = Column(Integer, primary_key=True, autoincrement=True)
    competitor_id = Column(
        Integer, ForeignKey("dim_competitor.competitor_id"), nullable=False
    )
    metric_id = Column(String, ForeignKey("dim_metric.metric_id"), nullable=False)
    date_id = Column(Integer, ForeignKey("dim_date.date_id"), nullable=True)
    geography_id = Column(Integer, ForeignKey("dim_geography.geography_id"), nullable=True)
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=True)
    observation_id = Column(
        Integer, ForeignKey("fact_observation.observation_id"), nullable=True
    )
    confidence = Column(Float, nullable=True)
    ingestion_timestamp = Column(DateTime, default=_utcnow, nullable=False)


class FactHypothesisTest(Base):
    """Result of a statistical hypothesis test, fully documented."""

    __tablename__ = "fact_hypothesis_test"

    test_id = Column(Integer, primary_key=True, autoincrement=True)
    hypothesis_name = Column(String, nullable=False)
    null_hypothesis = Column(Text, nullable=False)
    alternative_hypothesis = Column(Text, nullable=False)
    variable_1 = Column(String, nullable=True)
    variable_2 = Column(String, nullable=True)
    group_1 = Column(String, nullable=True)
    group_2 = Column(String, nullable=True)
    sample_size_1 = Column(Integer, nullable=True)
    sample_size_2 = Column(Integer, nullable=True)
    mean_1 = Column(Float, nullable=True)
    mean_2 = Column(Float, nullable=True)
    test_name = Column(String, nullable=False)  # e.g. "Welch's t-test"
    test_statistic = Column(Float, nullable=True)
    p_value = Column(Float, nullable=True)
    confidence_level = Column(Float, nullable=False, default=0.95)
    effect_size = Column(Float, nullable=True)
    conclusion = Column(Text, nullable=True)
    interpretation = Column(Text, nullable=True)  # plain-English, non-technical
    source_dataset = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class FactInsight(Base):
    """An evidence-backed insight generated from the analytical layer."""

    __tablename__ = "fact_insight"

    insight_id = Column(Integer, primary_key=True, autoincrement=True)
    insight_title = Column(String, nullable=False)
    insight_description = Column(Text, nullable=False)
    supporting_metric_id = Column(String, ForeignKey("dim_metric.metric_id"), nullable=True)
    evidence_source = Column(Text, nullable=True)  # document/observation references
    confidence = Column(Float, nullable=True)
    evidence_grade = Column(String, nullable=True)
    business_implication = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class FactMarketGap(Base):
    """A candidate market gap, classified by evidence strength."""

    __tablename__ = "fact_market_gap"

    gap_id = Column(Integer, primary_key=True, autoincrement=True)
    gap_title = Column(String, nullable=False)
    gap_description = Column(Text, nullable=False)
    gap_type = Column(String, nullable=True)
    # e.g. demand_supply / geographic / pricing / feature / customer_pain_point
    evidence_classification = Column(
        String, nullable=False
    )  # evidence_backed / derived / hypothesis
    supporting_evidence = Column(Text, nullable=True)
    geography_id = Column(Integer, ForeignKey("dim_geography.geography_id"), nullable=True)
    related_metric_id = Column(String, ForeignKey("dim_metric.metric_id"), nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class FactRecommendation(Base):
    """A strategic recommendation tied back to a market gap and evidence."""

    __tablename__ = "fact_recommendation"

    recommendation_id = Column(Integer, primary_key=True, autoincrement=True)
    recommendation_text = Column(Text, nullable=False)
    supporting_evidence = Column(Text, nullable=True)
    opportunity = Column(Text, nullable=True)
    risk = Column(Text, nullable=True)
    priority = Column(String, nullable=True)  # high/medium/low
    suggested_action = Column(Text, nullable=True)
    related_gap_id = Column(Integer, ForeignKey("fact_market_gap.gap_id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


# ===========================================================================
# Engine / table-creation helpers
# ===========================================================================


def get_engine(database_path: str) -> Engine:
    """Create a SQLAlchemy engine for the given SQLite file path."""
    return create_engine(f"sqlite:///{database_path}", echo=False, future=True)


def create_all_tables(engine: Engine) -> None:
    """Create every table defined in this module, if not already present."""
    Base.metadata.create_all(engine)


def all_table_names() -> list[str]:
    """Return every table name declared in this schema, for verification."""
    return sorted(Base.metadata.tables.keys())
