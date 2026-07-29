# Aaryatech Market Intelligence Engine

A local, Windows-friendly pipeline that turns raw market research
documents (PDFs, industry/company/annual/competitor/government reports,
CSV, Excel, JSON, text files) into a clean SQLite database, statistical
insights, market-gap analysis, strategic recommendations, and
Power BI-ready CSV exports.

This is the **Market Intelligence** product of a planned three-product
suite (Market Intelligence, Investment Intelligence, Audience & Growth
Intelligence). The data architecture is built to be reused by the other
two products later.

> **Status: project structure, database schema, and PDF ingestion +
> extraction (Phase 1) are working end-to-end against a real PDF.**
> Normalization, analytics, hypothesis testing, insights, and Power BI
> export have not been built yet. See "Current status" below.

---

## Current status

| Phase | Status |
|---|---|
| 1. Project structure | ✅ Done |
| 2. Database schema | ✅ Done (19 tables, verified with automated tests) |
| 3. Document ingestion (PDF) | ✅ Done — `scripts/run_phase1_pdf_pipeline.py` |
| 4. PDF text/table extraction | ✅ Done for PDF (text: PyMuPDF, tables: pdfplumber). CSV/Excel/JSON/text extraction not started. |
| 5. Bronze → Silver → Gold transformation | 🟡 Bronze only (raw text/table files + DB rows). Silver/Gold not started. |
| 6. Metric normalization & entity resolution | ⏳ Not started |
| 7. Analytical calculations | ⏳ Not started |
| 8. Hypothesis testing | ⏳ Not started |
| 9. Insight & market gap generation | ⏳ Not started |
| 10. Power BI-ready output generation | ⏳ Not started |
| 11. End-to-end testing | 🟡 Unit tests exist; full `run_pipeline.py` not built |

The full `python run_pipeline.py` command described below is the target
end state and does not exist yet. Today, use
`python scripts/run_phase1_pdf_pipeline.py` (see "Phase 1: PDF ingestion
and extraction" below).

---

## Project structure

```
aaryatech-market-intelligence-engine/
├── data/
│   ├── input/              # <-- PLACE YOUR RAW FILES HERE
│   │   ├── pdf/             # PDF reports (industry, company, annual, govt, competitor)
│   │   ├── csv/              # CSV datasets
│   │   ├── excel/            # Excel (.xlsx/.xls) datasets
│   │   ├── json/             # JSON datasets
│   │   └── text/             # Plain text files
│   ├── bronze/              # Raw extracted data (untouched, one-to-one with source)
│   │   ├── documents/        # Raw page-level text extracted from documents
│   │   ├── tables/           # Raw tables extracted from documents
│   │   └── structured/       # Raw copies of ingested CSV/Excel/JSON
│   ├── silver/              # Cleaned, standardized, normalized data
│   └── gold/
│       └── powerbi/          # Final Power BI-ready CSV exports
├── database/                # SQLite database file lives here
├── src/                      # All pipeline source code
│   ├── config.py              # Central path/config definitions
│   ├── db/                    # Database schema + initialization
│   ├── ingestion/              # (Phase 3 - not built yet)
│   ├── extraction/             # (Phase 4 - not built yet)
│   ├── normalization/          # (Phase 6 - not built yet)
│   ├── entity_resolution/      # (Phase 6 - not built yet)
│   ├── analytics/               # (Phase 7 - not built yet)
│   ├── hypothesis_testing/      # (Phase 8 - not built yet)
│   ├── insights/                 # (Phase 9 - not built yet)
│   ├── market_gaps/              # (Phase 9 - not built yet)
│   ├── recommendations/          # (Phase 9 - not built yet)
│   ├── powerbi_export/           # (Phase 10 - not built yet)
│   └── utils/                     # Shared helpers (logging, etc.)
├── scripts/
│   └── init_database.py     # Creates the SQLite database + schema
├── tests/                    # Automated tests
├── logs/                      # Pipeline log files
├── requirements.txt
├── .env.example
└── README.md
```

---

## Installation (Windows)

1. Install **Python 3.11** (or compatible) from https://www.python.org/downloads/
   and make sure "Add python.exe to PATH" is checked during install.

2. Open Command Prompt or PowerShell in the project folder and create a
   virtual environment:

   ```
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Install dependencies:

   ```
   pip install -r requirements.txt
   ```

   Notes:
   - OCR fallback (`pytesseract`) needs the separate Tesseract-OCR
     Windows installer: https://github.com/UB-Mannheim/tesseract/wiki
   - Advanced table extraction (`camelot-py`) is commented out in
     `requirements.txt` because it needs Ghostscript installed
     separately; the MVP uses `pdfplumber` as its primary table
     extractor instead.

4. (Optional) Copy `.env.example` to `.env` if you want to set an LLM API
   key or override the database path. **Not required** — the core
   pipeline runs fully offline.

---

## What works right now

### Create the database

```
python scripts/init_database.py
```

This creates `database/market_intelligence.db` with all 19 tables
(9 dimension tables + 10 fact tables). Safe to re-run — it never drops
existing data.

### Run the automated tests

```
pytest
```

Verifies the schema creates correctly, and that PDF text/table
extraction and document registration work correctly against a small
synthetic PDF generated during the test run.

---

## Phase 1: PDF ingestion and extraction

```
python scripts/run_phase1_pdf_pipeline.py
```

This scans `data/input/pdf/`, and for every PDF found there:

1. Computes a SHA-256 hash and registers the file in `dim_document`
   (re-running on the same file reuses the existing document_id instead
   of duplicating it).
2. Extracts text page-by-page using **PyMuPDF**.
3. Extracts tables page-by-page using **pdfplumber**.
4. Writes raw page text to
   `data/bronze/documents/doc_<id>_<name>/page_NNNN.txt`.
5. Writes raw extracted tables to
   `data/bronze/tables/doc_<id>_<name>/page_NNNN_table_NN.json`.
6. Loads page and table metadata into `fact_document_text` and
   `fact_extracted_table` in SQLite.
7. Writes an extraction log (`_extraction_log.json` in the bronze
   documents folder, and a timestamped copy under `logs/`).

**Nothing is fabricated or silently dropped.** Pages with little/no
extractable text are flagged `needs_review` (or OCR'd, if Tesseract-OCR
is installed and on PATH). Tables with mostly empty/unreadable cells are
flagged `needs_review` rather than trusted automatically. This phase
does **not** summarize the document, generate insights, resolve
entities, or run any statistics — it only proves the engine can reliably
read a real PDF and preserve everything it extracted with full
provenance.

Advanced table extraction via **Camelot** is not used in this MVP
because it requires a separate Ghostscript installation; pdfplumber
(pure Python, no extra system dependency) is used instead. This is a
documented limitation, not a silent gap — see "Known limitations"
below.

---

## Where to put your files

- **PDF reports** → `data/input/pdf/`
- **CSV datasets** → `data/input/csv/`
- **Excel datasets** → `data/input/excel/`
- **JSON datasets** → `data/input/json/`
- **Plain text files** → `data/input/text/`

You can place real files there now. Ingestion/extraction code that reads
from these folders has not been built yet — that is the next phase of
development.

---

## Database design summary

The schema (`src/db/schema.py`) uses a dimension/fact-table design:

**Dimension (master) tables**: `dim_project`, `dim_company`,
`dim_competitor`, `dim_geography`, `dim_date`, `dim_metric`,
`dim_source`, `dim_document`, `dim_entity`.

**Fact (analytical) tables**: `fact_document_text`,
`fact_extracted_table`, `fact_observation`, `fact_company_metric`,
`fact_market_metric`, `fact_competitor_metric`, `fact_hypothesis_test`,
`fact_insight`, `fact_market_gap`, `fact_recommendation`.

Key design decisions:

- **`dim_metric` is a metric registry.** New KPIs are added as rows
  (metric_id, name, unit, category, formula, ...), never as new
  database columns.
- **`fact_observation` is the provenance backbone.** Every standardized
  numeric fact traces back to one row here, preserving the original
  (as-reported) value/unit next to the standardized value/unit, plus
  source, document, page number, table reference, extraction method,
  confidence, and evidence grade.
- **Bronze / Silver / Gold separation** is physical (separate
  directories) as well as logical (`fact_document_text` /
  `fact_extracted_table` = Bronze; normalized `fact_observation` records
  = Silver; `fact_*_metric` and Power BI CSVs = Gold).

---

## Known limitations (current stage)

- Only PDF ingestion/extraction is built. CSV/Excel/JSON/text ingestion,
  normalization, entity resolution, analytics, hypothesis testing,
  insight generation, and Power BI export do not exist yet.
- `run_pipeline.py` (the unified end-to-end command) does not exist yet
  — use `scripts/run_phase1_pdf_pipeline.py` directly for now.
- Camelot-based table extraction is optional/deferred due to its
  Ghostscript dependency; pdfplumber is used instead and flags weak
  extractions as `needs_review` rather than silently trusting them.
- OCR fallback requires Tesseract-OCR installed separately; if it is
  not present, scanned/image-only pages are flagged `needs_review`
  instead of being OCR'd (never fabricated).
- `dim_source` (the publisher/source registry, e.g. "CBRE") is not yet
  auto-populated from PDFs — the MVP does not guess a source
  organization from a filename or Word-document author metadata, since
  that would risk misattributing the report's publisher. Raw PDF
  metadata (title/author/creator/dates) is preserved as-is in each
  document's extraction log for later manual or LLM-assisted
  classification.

## Next development phase

Phase 2 (data normalization): parse the raw Bronze-layer text/tables to
identify metric names, values, units, geography, company/competitor
names, and time periods, standardize them where confidence is
sufficient, and load the results into `fact_observation` with full
provenance. Also extend document ingestion to CSV/Excel/JSON/text file
types.
