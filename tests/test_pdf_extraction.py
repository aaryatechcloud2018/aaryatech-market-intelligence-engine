"""
Tests for Phase 1 PDF ingestion/extraction (src/ingestion, src/extraction).

Uses a tiny synthetic PDF generated on the fly (instead of the large
real-world source PDF) so the test suite stays fast. The real PDF is
exercised via scripts/run_phase1_pdf_pipeline.py, not in the automated
test suite.
"""

from __future__ import annotations

import fitz
import pytest
from sqlalchemy.orm import sessionmaker

from src.db.schema import create_all_tables, get_engine
from src.extraction.pdf_extractor import extract_pdf
from src.ingestion.pdf_ingestion import compute_file_hash, register_document


@pytest.fixture()
def sample_pdf(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()

    page1 = doc.new_page()
    page1.insert_text((72, 72), "Sample Market Report\nRevenue grew 12% year over year.")

    page2 = doc.new_page()
    # A blank page, to exercise the needs_review path for empty/near-empty pages.

    doc.save(pdf_path)
    doc.close()
    return pdf_path


def test_extract_pdf_returns_page_and_table_results(sample_pdf):
    pages, tables, summary = extract_pdf(sample_pdf, ocr_enabled=False)

    assert summary.page_count == 2
    assert len(pages) == 2
    assert pages[0].status == "success"
    assert "Revenue grew 12%" in pages[0].text
    # Blank second page should be flagged, not silently dropped.
    assert pages[1].status == "needs_review"
    assert isinstance(tables, list)


def test_compute_file_hash_is_deterministic(sample_pdf):
    h1 = compute_file_hash(sample_pdf)
    h2 = compute_file_hash(sample_pdf)
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex digest length


def test_register_document_is_idempotent(sample_pdf):
    engine = get_engine(":memory:")
    create_all_tables(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        doc1, created1 = register_document(session, sample_pdf)
        session.commit()
        first_id = doc1.document_id
        assert created1 is True

        doc2, created2 = register_document(session, sample_pdf)
        assert created2 is False
        assert doc2.document_id == first_id
