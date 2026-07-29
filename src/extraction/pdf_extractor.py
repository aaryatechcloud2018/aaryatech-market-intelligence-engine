"""
PDF text and table extraction (Bronze layer).

Text extraction uses PyMuPDF (``fitz``) - fast and reliable for
digitally-generated PDFs, and processed one page at a time rather than
loading the whole document's text into memory at once.

Table extraction uses ``pdfplumber``, a pure-Python library with no
external system dependency (unlike Camelot, which needs Ghostscript
installed separately - see requirements.txt for notes). pdfplumber is
therefore the primary/only table extractor in this MVP; Camelot support
can be added later as an optional second pass without changing this
module's output contract.

Nothing here fabricates content. Pages that look like scanned images
(little or no extractable text) are flagged ``needs_review`` unless an
OCR fallback (pytesseract + a working Tesseract-OCR install) is actually
available, in which case OCR is attempted and the result is clearly
tagged with extraction_method="ocr_tesseract". Tables extracted with low
cell-fill confidence are flagged ``needs_review`` rather than trusted
silently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
import pdfplumber

from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# A page with fewer extractable characters than this is treated as a
# likely scanned/image-only page rather than a normal digital page.
MIN_TEXT_CHARS_FOR_DIGITAL_PAGE = 20

# Tables with fewer total cells than this are too small to trust blindly.
MIN_TABLE_CELLS_FOR_CONFIDENCE = 4

# Below this fraction of non-empty cells, a table is flagged for review.
MIN_TABLE_FILL_CONFIDENCE = 0.4

try:
    import pytesseract
    from PIL import Image

    _OCR_LIBS_IMPORTED = True
except ImportError:
    _OCR_LIBS_IMPORTED = False


def tesseract_available() -> bool:
    """True only if pytesseract AND a working Tesseract-OCR binary are present."""
    if not _OCR_LIBS_IMPORTED:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


@dataclass
class PageResult:
    page_number: int
    text: str
    char_count: int
    status: str  # success / needs_review / failed
    extraction_method: str
    error_message: str | None = None


@dataclass
class TableResult:
    page_number: int
    table_index: int
    table_reference: str
    rows: list[list[Any]]
    row_count: int
    column_count: int
    status: str  # success / needs_review
    confidence: float | None
    review_reason: str | None
    extraction_method: str = "pdfplumber"


@dataclass
class ExtractionSummary:
    file_name: str
    page_count: int
    pages_success: int = 0
    pages_needs_review: int = 0
    pages_failed: int = 0
    tables_detected: int = 0
    tables_success: int = 0
    tables_needs_review: int = 0
    ocr_pages_attempted: int = 0
    is_likely_scanned_document: bool = False
    errors: list[str] = field(default_factory=list)


def _extract_text_pages(pdf_doc: fitz.Document, ocr_available: bool, summary: ExtractionSummary) -> list[PageResult]:
    results: list[PageResult] = []

    for i in range(pdf_doc.page_count):
        page_number = i + 1
        try:
            page = pdf_doc[i]
            text = page.get_text("text") or ""
            char_count = len(text.strip())

            if char_count >= MIN_TEXT_CHARS_FOR_DIGITAL_PAGE:
                results.append(
                    PageResult(
                        page_number=page_number,
                        text=text,
                        char_count=char_count,
                        status="success",
                        extraction_method="pymupdf_text",
                    )
                )
                continue

            # Little/no text found -> likely a scanned or image-only page.
            if ocr_available:
                summary.ocr_pages_attempted += 1
                try:
                    pix = page.get_pixmap(dpi=300)
                    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                    ocr_text = pytesseract.image_to_string(img)
                    ocr_char_count = len(ocr_text.strip())
                    results.append(
                        PageResult(
                            page_number=page_number,
                            text=ocr_text,
                            char_count=ocr_char_count,
                            status="success" if ocr_char_count > 0 else "needs_review",
                            extraction_method="ocr_tesseract",
                            error_message=None if ocr_char_count > 0 else "OCR produced no text",
                        )
                    )
                except Exception as exc:  # OCR failure must not crash the pipeline
                    logger.warning("OCR failed on page %d: %s", page_number, exc)
                    results.append(
                        PageResult(
                            page_number=page_number,
                            text="",
                            char_count=0,
                            status="failed",
                            extraction_method="ocr_tesseract",
                            error_message=f"OCR error: {exc}",
                        )
                    )
            else:
                results.append(
                    PageResult(
                        page_number=page_number,
                        text=text,
                        char_count=char_count,
                        status="needs_review",
                        extraction_method="pymupdf_text",
                        error_message=(
                            "Likely scanned/image page with little or no extractable "
                            "text; OCR fallback unavailable (Tesseract-OCR is not "
                            "installed in this environment)."
                        ),
                    )
                )
        except Exception as exc:  # a single bad page must not abort the whole document
            logger.error("Text extraction failed on page %d: %s", page_number, exc)
            results.append(
                PageResult(
                    page_number=page_number,
                    text="",
                    char_count=0,
                    status="failed",
                    extraction_method="pymupdf_text",
                    error_message=str(exc),
                )
            )
    return results


def _assess_table_confidence(rows: list[list[Any]]) -> tuple[float, str | None]:
    """Heuristic confidence: fraction of non-empty cells. Flags weak extractions for review."""
    total_cells = sum(len(r) for r in rows)
    if total_cells == 0:
        return 0.0, "Table has no cells"

    filled_cells = sum(1 for r in rows for c in r if c not in (None, ""))
    confidence = filled_cells / total_cells

    if total_cells < MIN_TABLE_CELLS_FOR_CONFIDENCE:
        return confidence, "Table is very small (may be a false-positive detection)"
    if confidence < MIN_TABLE_FILL_CONFIDENCE:
        return confidence, "Many empty/unreadable cells detected in this table"
    return confidence, None


def _extract_tables(pdf_path: Path) -> list[TableResult]:
    results: list[TableResult] = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_number = i + 1
            try:
                raw_tables = page.extract_tables()
            except Exception as exc:
                logger.warning("Table extraction failed on page %d: %s", page_number, exc)
                continue

            for t_idx, table in enumerate(raw_tables, start=1):
                if not table:
                    continue
                confidence, reason = _assess_table_confidence(table)
                status = "needs_review" if reason else "success"
                results.append(
                    TableResult(
                        page_number=page_number,
                        table_index=t_idx,
                        table_reference=f"Page {page_number}, Table {t_idx}",
                        rows=table,
                        row_count=len(table),
                        column_count=max((len(r) for r in table), default=0),
                        status=status,
                        confidence=round(confidence, 3),
                        review_reason=reason,
                    )
                )
    return results


def extract_pdf(
    pdf_path: Path, ocr_enabled: bool = True
) -> tuple[list[PageResult], list[TableResult], ExtractionSummary]:
    """
    Run full text + table extraction over a PDF file.

    Returns (page_results, table_results, summary). Never raises for
    page/table-level failures - those are captured in the results and
    summary instead, so a single bad page/table cannot abort ingestion
    of the rest of the document.
    """
    ocr_available = ocr_enabled and tesseract_available()
    if ocr_enabled and not ocr_available:
        logger.warning(
            "OCR fallback requested but Tesseract-OCR is not available in this "
            "environment; scanned pages will be flagged NEEDS_REVIEW instead of "
            "being OCR'd."
        )

    pdf_doc = fitz.open(pdf_path)
    try:
        page_count = pdf_doc.page_count
        summary = ExtractionSummary(file_name=pdf_path.name, page_count=page_count)
        pages = _extract_text_pages(pdf_doc, ocr_available, summary)
    finally:
        pdf_doc.close()

    tables = _extract_tables(pdf_path)

    for p in pages:
        if p.status == "success":
            summary.pages_success += 1
        elif p.status == "needs_review":
            summary.pages_needs_review += 1
        else:
            summary.pages_failed += 1
            summary.errors.append(f"Page {p.page_number}: {p.error_message}")

    summary.is_likely_scanned_document = (
        page_count > 0
        and (summary.pages_needs_review + summary.pages_failed) > (page_count * 0.5)
    )

    summary.tables_detected = len(tables)
    for t in tables:
        if t.status == "success":
            summary.tables_success += 1
        else:
            summary.tables_needs_review += 1

    return pages, tables, summary
