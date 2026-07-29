"""
Phase 1 CLI entry point.

    REAL PDF -> PDF INGESTION -> TEXT EXTRACTION -> TABLE EXTRACTION
    -> BRONZE RAW DATA -> SQLITE MASTER DATABASE

Usage (from the project root):

    python scripts/run_phase1_pdf_pipeline.py

Scans data/input/pdf/, registers every PDF found there in the master
database, extracts page-level text and tables, writes the raw
extraction to data/bronze/, and loads the extraction metadata into
SQLite. Does not summarize, generate insights, or run statistics -
that is later phases.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import BRONZE_DOCUMENTS_DIR, BRONZE_TABLES_DIR, DATABASE_PATH
from src.ingestion.pdf_pipeline import run_pdf_ingestion_phase


def main() -> None:
    print("=" * 70)
    print("PHASE 1: PDF INGESTION + TEXT/TABLE EXTRACTION -> BRONZE + SQLITE")
    print("=" * 70)

    results = run_pdf_ingestion_phase()

    if not results:
        print("\nNo PDF files were found in data/input/pdf/. Nothing to do.")
        return

    for r in results:
        print("\n" + "-" * 70)
        print(f"FILE: {r['file_name']}")
        if r["status"] == "failed" and "page_count" not in r:
            print(f"  STATUS: FAILED - could not extract this PDF at all.")
            print(f"  ERROR: {r['error']}")
            continue

        print(f"  document_id            : {r['document_id']}")
        print(f"  overall status         : {r['status'].upper()}")
        print(f"  pages total            : {r['page_count']}")
        print(f"  pages extracted OK     : {r['pages_success']}")
        print(f"  pages needing review   : {r['pages_needs_review']}")
        print(f"  pages failed           : {r['pages_failed']}")
        print(f"  tables detected        : {r['tables_detected']}")
        print(f"  tables extracted OK    : {r['tables_success']}")
        print(f"  tables needing review  : {r['tables_needs_review']}")
        print(f"  OCR pages attempted    : {r['ocr_pages_attempted']}")
        print(f"  likely scanned doc     : {r['is_likely_scanned_document']}")
        if r["errors"]:
            print(f"  errors ({len(r['errors'])}):")
            for err in r["errors"][:10]:
                print(f"    - {err}")
        print(f"  bronze text dir        : {r['bronze_documents_dir']}")
        print(f"  bronze tables dir      : {r['bronze_tables_dir']}")
        print(f"  extraction log         : {r['extraction_log_path']}")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Database          : {DATABASE_PATH}")
    print(f"  Bronze documents  : {BRONZE_DOCUMENTS_DIR}")
    print(f"  Bronze tables     : {BRONZE_TABLES_DIR}")
    print(f"  PDFs processed    : {len(results)}")


if __name__ == "__main__":
    main()
