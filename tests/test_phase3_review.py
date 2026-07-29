import json

from sqlalchemy.orm import sessionmaker

from src.db.schema import DimDocument, FactDocumentText, FactExtractedTable, create_all_tables, get_engine
from src.normalization.phase2_pipeline import process_document_phase2, seed_metric_registry
from src.normalization.phase3_review import (
    _ANALYSIS_READY_FIELDNAMES,
    _REVIEW_FIELDNAMES,
    _REVIEW_STATUSES,
    _load_enriched_observations,
    STATUS_ANALYSIS_READY,
    export_analysis_ready,
    export_data_quality_summary,
    export_low_confidence_metric_summary,
    export_low_confidence_review,
)


def _make_session():
    engine = get_engine(":memory:")
    create_all_tables(engine)
    return sessionmaker(bind=engine)()


def _seed_document_with_mixed_observations(session, tmp_path):
    document = DimDocument(
        file_name="test.pdf", file_path="/tmp/test.pdf", file_type="pdf",
        file_hash="abc123", extraction_status="success",
    )
    session.add(document)
    session.flush()

    session.add(
        FactDocumentText(
            document_id=document.document_id, page_number=1,
            text_content="TEST SUBJECT COMPANY LIMITED\nAnnual Report",
            extraction_method="pymupdf_text", extraction_status="success",
        )
    )

    # A clean table -> should end up ANALYSIS_READY (clear period, clean values).
    clean_table = FactExtractedTable(
        document_id=document.document_id, page_number=10, table_reference="Page 10, Table 1",
        table_data_json=json.dumps([
            ["Particulars", "Fiscal 2025", "Fiscal 2024"],
            ["Revenue from operations", "1,234.5", "1,000.0"],
        ]),
        row_count=2, column_count=3,
        extraction_method="pdfplumber", extraction_status="success", confidence=0.95,
    )
    # A table with no detectable period -> should end up INSUFFICIENT_CONTEXT.
    no_period_table = FactExtractedTable(
        document_id=document.document_id, page_number=20, table_reference="Page 20, Table 1",
        table_data_json=json.dumps([
            ["Particulars", "Value"],
            ["EBITDA", "300.1"],
        ]),
        row_count=1, column_count=2,
        extraction_method="pdfplumber", extraction_status="success", confidence=0.9,
    )
    session.add_all([clean_table, no_period_table])
    session.flush()
    session.commit()
    return document


def test_phase3_pipeline_end_to_end():
    session = _make_session()
    seed_metric_registry(session)
    document = _seed_document_with_mixed_observations(session, None)
    process_document_phase2(session, document)

    observations = _load_enriched_observations(session)
    assert len(observations) > 0

    # 1. Every observation is assigned a valid status.
    for obs in observations:
        assert obs["status"] in (STATUS_ANALYSIS_READY,) + _REVIEW_STATUSES

    statuses_present = {o["status"] for o in observations}
    assert STATUS_ANALYSIS_READY in statuses_present
    assert statuses_present & set(_REVIEW_STATUSES)  # at least one review-required record too

    # 6. Metric names are populated where possible (never blank).
    for obs in observations:
        assert obs["metric_name"]


def test_analysis_ready_export_contains_only_analysis_ready(tmp_path, monkeypatch):
    import src.normalization.phase3_review as phase3_module

    monkeypatch.setattr(phase3_module, "SILVER_DIR", tmp_path)

    session = _make_session()
    seed_metric_registry(session)
    document = _seed_document_with_mixed_observations(session, None)
    process_document_phase2(session, document)
    observations = _load_enriched_observations(session)

    path = export_analysis_ready(observations)
    assert path.exists()

    import csv
    with open(path) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) > 0
    for row in rows:
        assert row["status"] == STATUS_ANALYSIS_READY
    assert set(rows[0].keys()) == set(_ANALYSIS_READY_FIELDNAMES)


def test_low_confidence_review_export_contains_only_review_records(tmp_path, monkeypatch):
    import src.normalization.phase3_review as phase3_module

    monkeypatch.setattr(phase3_module, "SILVER_DIR", tmp_path)

    session = _make_session()
    seed_metric_registry(session)
    document = _seed_document_with_mixed_observations(session, None)
    process_document_phase2(session, document)
    observations = _load_enriched_observations(session)

    path = export_low_confidence_review(observations)
    assert path.exists()

    import csv
    with open(path) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) > 0
    for row in rows:
        assert row["status"] in _REVIEW_STATUSES
    assert set(rows[0].keys()) == set(_REVIEW_FIELDNAMES)


def test_no_observations_deleted_and_page_provenance_preserved():
    session = _make_session()
    seed_metric_registry(session)
    document = _seed_document_with_mixed_observations(session, None)
    process_document_phase2(session, document)

    from src.db.schema import FactObservation
    db_count = session.query(FactObservation).count()

    observations = _load_enriched_observations(session)
    assert len(observations) == db_count  # nothing dropped by the Phase 3 read layer

    # Every Phase 3 record must retain the page it came from.
    for obs in observations:
        assert obs["page_number"] is not None

    analysis_ready = [o for o in observations if o["status"] == STATUS_ANALYSIS_READY]
    review = [o for o in observations if o["status"] in _REVIEW_STATUSES]
    assert len(analysis_ready) + len(review) == len(observations)


def test_metric_summary_and_quality_summary_exports(tmp_path, monkeypatch):
    import src.normalization.phase3_review as phase3_module

    monkeypatch.setattr(phase3_module, "SILVER_DIR", tmp_path)

    session = _make_session()
    seed_metric_registry(session)
    document = _seed_document_with_mixed_observations(session, None)
    process_document_phase2(session, document)
    observations = _load_enriched_observations(session)

    export_low_confidence_review(observations)  # metric summary is derived from review rows
    metric_summary_path = export_low_confidence_metric_summary(observations)
    quality_path, quality_summary = export_data_quality_summary(observations)

    assert metric_summary_path.exists()
    assert quality_path.exists()
    assert quality_summary["total_observations"] == len(observations)
    assert (
        quality_summary["analysis_ready"]
        + quality_summary["needs_review"]
        + quality_summary["duplicates"]
        + quality_summary["conflicts"]
        + quality_summary["insufficient_context"]
        == len(observations)
    )
