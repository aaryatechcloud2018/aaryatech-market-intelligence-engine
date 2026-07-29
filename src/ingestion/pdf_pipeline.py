"""
Phase 1 pipeline: REAL PDF -> ingestion -> text/table extraction ->
Bronze raw data files -> SQLite master database.

This module does NOT summarize, generate insights, resolve entities, or
run any statistics. Its only job is to prove the engine can reliably
read a real PDF and preserve everything it extracted, with full
provenance and without silently discarding anything.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from src.config import (
    BRONZE_DOCUMENTS_DIR,
    BRONZE_TABLES_DIR,
    LOG_DIR,
)
from src.db.init_db import initialize_database
from src.db.schema import DimDocument, FactDocumentText, FactExtractedTable
from src.extraction.pdf_extractor import (
    ExtractionSummary,
    PageResult,
    TableResult,
    extract_pdf,
    tesseract_available,
)
from src.ingestion.pdf_ingestion import register_document, scan_pdf_input_dir
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    return slug[:60] if slug else "document"


def _document_folder_name(document: DimDocument) -> str:
    stem = Path(document.file_name).stem
    return f"doc_{document.document_id:05d}_{_slugify(stem)}"


def _read_pdf_metadata(pdf_path: Path) -> dict:
    """Read raw PDF metadata as reported by the file itself (no inference)."""
    import fitz

    doc = fitz.open(pdf_path)
    try:
        meta = dict(doc.metadata or {})
        meta["page_count"] = doc.page_count
    finally:
        doc.close()
    return meta


def _write_bronze_pages(pages: list[PageResult], doc_dir: Path) -> None:
    doc_dir.mkdir(parents=True, exist_ok=True)
    for page in pages:
        page_file = doc_dir / f"page_{page.page_number:04d}.txt"
        page_file.write_text(page.text or "", encoding="utf-8")


def _write_bronze_tables(tables: list[TableResult], doc_dir: Path) -> None:
    doc_dir.mkdir(parents=True, exist_ok=True)
    for table in tables:
        table_file = doc_dir / f"page_{table.page_number:04d}_table_{table.table_index:02d}.json"
        table_file.write_text(
            json.dumps(
                {
                    "page_number": table.page_number,
                    "table_index": table.table_index,
                    "table_reference": table.table_reference,
                    "status": table.status,
                    "confidence": table.confidence,
                    "review_reason": table.review_reason,
                    "extraction_method": table.extraction_method,
                    "rows": table.rows,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def _load_pages_into_db(session: Session, document_id: int, pages: list[PageResult]) -> None:
    for page in pages:
        session.add(
            FactDocumentText(
                document_id=document_id,
                page_number=page.page_number,
                text_content=page.text if page.text else None,
                char_count=page.char_count,
                extraction_method=page.extraction_method,
                extraction_status=page.status,
                error_message=page.error_message,
            )
        )


def _load_tables_into_db(session: Session, document_id: int, tables: list[TableResult]) -> None:
    for table in tables:
        session.add(
            FactExtractedTable(
                document_id=document_id,
                page_number=table.page_number,
                table_reference=table.table_reference,
                table_data_json=json.dumps(table.rows, ensure_ascii=False),
                row_count=table.row_count,
                column_count=table.column_count,
                extraction_method=table.extraction_method,
                extraction_status=table.status,
                confidence=table.confidence,
                review_reason=table.review_reason,
            )
        )


def _write_extraction_log(
    summary: ExtractionSummary,
    document: DimDocument,
    doc_dir_documents: Path,
    pdf_metadata: dict,
) -> Path:
    log = {
        "document_id": document.document_id,
        "file_name": summary.file_name,
        "file_path": document.file_path,
        "file_hash": document.file_hash,
        "pdf_metadata_as_reported": pdf_metadata,
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "page_count": summary.page_count,
        "pages_success": summary.pages_success,
        "pages_needs_review": summary.pages_needs_review,
        "pages_failed": summary.pages_failed,
        "tables_detected": summary.tables_detected,
        "tables_success": summary.tables_success,
        "tables_needs_review": summary.tables_needs_review,
        "ocr_pages_attempted": summary.ocr_pages_attempted,
        "tesseract_available": tesseract_available(),
        "is_likely_scanned_document": summary.is_likely_scanned_document,
        "errors": summary.errors,
    }

    doc_dir_documents.mkdir(parents=True, exist_ok=True)
    log_path = doc_dir_documents / "_extraction_log.json"
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

    # Also drop a copy under logs/ for a single central place to find all runs.
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    central_log_path = LOG_DIR / f"pdf_extraction_doc{document.document_id:05d}_{ts}.json"
    central_log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

    return log_path


def process_single_pdf(session: Session, pdf_path: Path) -> dict:
    """Ingest + extract one PDF end-to-end. Returns the run summary as a dict."""
    logger.info("Processing PDF: %s", pdf_path)

    document, created = register_document(session, pdf_path)
    pdf_metadata = _read_pdf_metadata(pdf_path)

    try:
        pages, tables, summary = extract_pdf(pdf_path)
    except Exception as exc:
        # The PDF could not be opened/read at all. Never discard it silently -
        # record the failure against the document row instead.
        logger.error("Failed to extract PDF %s: %s", pdf_path.name, exc)
        document.extraction_status = "failed"
        document.error_message = f"Could not open/extract PDF: {exc}"
        session.commit()
        return {
            "file_name": pdf_path.name,
            "document_id": document.document_id,
            "status": "failed",
            "error": str(document.error_message),
        }

    doc_folder = _document_folder_name(document)
    documents_dir = BRONZE_DOCUMENTS_DIR / doc_folder
    tables_dir = BRONZE_TABLES_DIR / doc_folder

    _write_bronze_pages(pages, documents_dir)
    _write_bronze_tables(tables, tables_dir)
    _load_pages_into_db(session, document.document_id, pages)
    _load_tables_into_db(session, document.document_id, tables)

    if summary.pages_failed == 0 and summary.pages_needs_review == 0:
        status = "success"
    elif summary.pages_success > 0:
        status = "partial"
    else:
        status = "failed"

    method_parts = ["pymupdf_text", "pdfplumber_tables"]
    if summary.ocr_pages_attempted > 0:
        method_parts.append("ocr_tesseract")

    document.page_count = summary.page_count
    document.extraction_status = status
    document.extraction_method = "+".join(method_parts)
    document.is_scanned = summary.is_likely_scanned_document
    document.error_message = "; ".join(summary.errors[:10]) if summary.errors else None

    session.commit()

    log_path = _write_extraction_log(summary, document, documents_dir, pdf_metadata)

    return {
        "file_name": pdf_path.name,
        "document_id": document.document_id,
        "document_created": created,
        "status": status,
        "page_count": summary.page_count,
        "pages_success": summary.pages_success,
        "pages_needs_review": summary.pages_needs_review,
        "pages_failed": summary.pages_failed,
        "tables_detected": summary.tables_detected,
        "tables_success": summary.tables_success,
        "tables_needs_review": summary.tables_needs_review,
        "ocr_pages_attempted": summary.ocr_pages_attempted,
        "is_likely_scanned_document": summary.is_likely_scanned_document,
        "errors": summary.errors,
        "bronze_documents_dir": str(documents_dir),
        "bronze_tables_dir": str(tables_dir),
        "extraction_log_path": str(log_path),
    }


def run_pdf_ingestion_phase() -> list[dict]:
    """Scan data/input/pdf, and ingest + extract every PDF found there."""
    engine = initialize_database()
    session_factory = sessionmaker(bind=engine)

    pdf_files = scan_pdf_input_dir()
    if not pdf_files:
        logger.warning("No PDF files found in the input directory.")
        return []

    results = []
    for pdf_path in pdf_files:
        with session_factory() as session:
            result = process_single_pdf(session, pdf_path)
            results.append(result)

    return results
