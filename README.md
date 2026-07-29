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

> **Status: project structure + database schema only.**
> The ingestion/extraction/analytics pipeline has not been built yet.
> See "Current status" below for exactly what works today.

---

## Current status

| Phase | Status |
|---|---|
| 1. Project structure | ✅ Done |
| 2. Database schema | ✅ Done (19 tables, verified with automated tests) |
| 3. Document ingestion | ⏳ Not started |
| 4. PDF/Excel/CSV/JSON/text extraction | ⏳ Not started |
| 5. Bronze → Silver → Gold transformation | ⏳ Not started |
| 6. Metric normalization & entity resolution | ⏳ Not started |
| 7. Analytical calculations | ⏳ Not started |
| 8. Hypothesis testing | ⏳ Not started |
| 9. Insight & market gap generation | ⏳ Not started |
| 10. Power BI-ready output generation | ⏳ Not started |
| 11. End-to-end testing | ⏳ Not started |

The full `python run_pipeline.py` command described below is the target
end state and does not exist yet.

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

This verifies the schema creates correctly and contains every expected
table.

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

- No ingestion, extraction, normalization, analytics, hypothesis
  testing, insight generation, or Power BI export code exists yet — only
  the project skeleton and database schema.
- `run_pipeline.py` does not exist yet.
- Camelot-based table extraction is optional/deferred due to its
  Ghostscript dependency.

## Next development phase

Phase 3 (document ingestion): recursively scan `data/input/`, register
each file in `dim_document` with a unique ID, hash, and ingestion
timestamp, and log every file (including failures) without silently
discarding any of them.
