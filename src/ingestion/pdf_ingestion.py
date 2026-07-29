"""
PDF ingestion: discover PDF files in the input directory and register
each one in the master database (dim_document) before extraction runs.

Registration is idempotent: re-running the pipeline on the same file
(matched by SHA-256 content hash) reuses the existing document_id
instead of creating a duplicate row.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy.orm import Session

from src.config import INPUT_PDF_DIR
from src.db.schema import DimDocument
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def scan_pdf_input_dir(pdf_dir: Path = INPUT_PDF_DIR) -> list[Path]:
    """Recursively find every PDF file under the input directory."""
    if not pdf_dir.exists():
        logger.warning("PDF input directory does not exist: %s", pdf_dir)
        return []
    return sorted(p for p in pdf_dir.rglob("*.pdf") if p.is_file())


def compute_file_hash(file_path: Path, chunk_size: int = 1024 * 1024) -> str:
    """SHA-256 hash of the file, read in chunks so large PDFs never fully load into memory."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def register_document(session: Session, file_path: Path) -> tuple[DimDocument, bool]:
    """
    Insert (or find) the dim_document row for this PDF.

    Returns (document, created) where created=False means a document
    with the same file content hash already existed and was reused.
    """
    file_hash = compute_file_hash(file_path)

    existing = (
        session.query(DimDocument)
        .filter(DimDocument.file_hash == file_hash)
        .one_or_none()
    )
    if existing is not None:
        logger.info(
            "Document already registered (content hash match): %s -> document_id=%s",
            file_path.name,
            existing.document_id,
        )
        return existing, False

    document = DimDocument(
        file_name=file_path.name,
        file_path=str(file_path.resolve()),
        file_type="pdf",
        file_hash=file_hash,
        file_size_bytes=file_path.stat().st_size,
        extraction_status="pending",
    )
    session.add(document)
    session.flush()  # assigns document_id without committing the transaction
    logger.info("Registered new document: %s -> document_id=%s", file_path.name, document.document_id)
    return document, True
