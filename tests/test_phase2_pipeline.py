import json

from sqlalchemy.orm import sessionmaker

from src.db.schema import DimDocument, FactExtractedTable, FactObservation, create_all_tables, get_engine
from src.normalization.phase2_pipeline import (
    export_data_quality_report,
    export_entity_registry,
    export_metric_registry,
    export_observation_csvs,
    export_table_classification_report,
    process_document_phase2,
    seed_metric_registry,
)


def _make_session():
    engine = get_engine(":memory:")
    create_all_tables(engine)
    return sessionmaker(bind=engine)()


def test_process_document_phase2_end_to_end(tmp_path, monkeypatch):
    import src.normalization.phase2_pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "SILVER_OBSERVATIONS_DIR", tmp_path / "observations")
    monkeypatch.setattr(pipeline_module, "SILVER_REPORTS_DIR", tmp_path / "reports")

    session = _make_session()
    seed_metric_registry(session)

    document = DimDocument(
        file_name="test.pdf", file_path="/tmp/test.pdf", file_type="pdf",
        file_hash="abc123", extraction_status="success",
    )
    session.add(document)
    session.flush()

    financial_table = FactExtractedTable(
        document_id=document.document_id,
        page_number=10,
        table_reference="Page 10, Table 1",
        table_data_json=json.dumps([
            ["Particulars", "Fiscal 2025", "Fiscal 2024"],
            ["Revenue from operations", "1,234.5", "1,000.0"],
            ["EBITDA", "300.1", "250.0"],
        ]),
        row_count=3, column_count=3,
        extraction_method="pdfplumber", extraction_status="success", confidence=0.95,
    )
    glossary_table = FactExtractedTable(
        document_id=document.document_id,
        page_number=3,
        table_reference="Page 3, Table 1",
        table_data_json=json.dumps([
            ["Term", "Description"],
            ["Shareholders", "means the holders of equity shares"],
        ]),
        row_count=2, column_count=2,
        extraction_method="pdfplumber", extraction_status="success", confidence=0.9,
    )
    session.add_all([financial_table, glossary_table])
    session.flush()
    session.commit()

    summary = process_document_phase2(session, document)

    assert summary["tables_total"] == 2
    assert summary["tables_irrelevant"] >= 1  # glossary table
    assert summary["observations_created"] == 4  # 2 metrics x 2 periods

    observations = session.query(FactObservation).all()
    assert len(observations) == 4
    metric_ids = {o.metric_id for o in observations}
    assert metric_ids == {"total_revenue", "ebitda"}

    # every observation must carry full provenance back to page + table
    for obs in observations:
        assert obs.page_number == 10
        assert obs.table_reference == "Page 10, Table 1"
        assert obs.document_id == document.document_id
        assert obs.original_value is not None
        assert obs.confidence is not None
        assert obs.evidence_grade in ("A", "B", "C")

    files = export_observation_csvs(session, document.document_id)
    assert (tmp_path / "observations" / "fact_observations_all.csv").exists()
    assert (tmp_path / "observations" / "fact_observations_high_confidence.csv").exists()
    assert (tmp_path / "observations" / "fact_observations_needs_review.csv").exists()

    classification_report = export_table_classification_report(session, document.document_id)
    metric_registry = export_metric_registry(session)
    entity_registry = export_entity_registry(session)
    quality_report = export_data_quality_report(summary)

    for path in (classification_report, metric_registry, entity_registry, quality_report):
        assert path
