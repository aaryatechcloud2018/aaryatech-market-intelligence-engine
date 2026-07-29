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

> **Status: Phases 1-2 are working end-to-end against a real 583-page
> PDF** (a Red Herring Prospectus). Analytics, hypothesis testing,
> insights, and Power BI export have not been built yet. See "Current
> status" below.

---

## Current status

| Phase | Status |
|---|---|
| 1. Project structure | ✅ Done |
| 2. Database schema | ✅ Done (19 tables, verified with automated tests) |
| 3. Document ingestion (PDF) | ✅ Done — `scripts/run_phase1_pdf_pipeline.py` |
| 4. PDF text/table extraction | ✅ Done for PDF (text: PyMuPDF, tables: pdfplumber). CSV/Excel/JSON/text extraction not started. |
| 5. Bronze → Silver → Gold transformation | 🟡 Bronze + Silver done. Gold/Power BI export not started. |
| 6. Metric normalization & entity resolution | ✅ Done — `scripts/run_phase2_normalization.py` (rule-based table classification, metric extraction, unit/period normalization, entity resolution, QC) |
| 7. Analytical calculations | ⏳ Not started |
| 8. Hypothesis testing | ⏳ Not started |
| 9. Insight & market gap generation | ⏳ Not started |
| 10. Power BI-ready output generation | ⏳ Not started |
| 11. End-to-end testing | 🟡 28 unit/integration tests exist; full `run_pipeline.py` not built |

The full `python run_pipeline.py` command described below is the target
end state and does not exist yet. Today, use
`python scripts/run_phase1_pdf_pipeline.py` then
`python scripts/run_phase2_normalization.py` (see the Phase sections
below).

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

## Phase 2: table classification and normalization

```
python scripts/run_phase2_normalization.py
```

Reads the Bronze-layer tables loaded by Phase 1 and, for every document:

1. **Classifies** every extracted table into one of 14 categories
   (MARKET, COMPANY, COMPETITOR, FINANCIAL, OPERATIONAL, GEOGRAPHIC,
   CUSTOMER, PRICING, INDUSTRY, RISK, LEGAL, GOVERNANCE, OTHER,
   IRRELEVANT) using a deterministic, auditable keyword-matching
   classifier (`src/normalization/table_classifier.py`) - no LLM
   required, consistent with the MVP's offline-first constraint.
2. **Scores relevance** (0-1) and **classification confidence** (0-1)
   per table, prioritizing categories useful for Market Intelligence.
3. **Extracts metrics**: for tables not classified IRRELEVANT, scans
   row labels against a keyword-based metric registry
   (`src/normalization/metric_definitions.py` - revenue, EBITDA,
   margins, occupancy, seating capacity, number of centers, client
   concentration, market size/growth, etc.) and pulls out every numeric
   cell that matches, handling multi-row AND multi-column headers
   (e.g. a company name spanning several columns with year sub-headers
   beneath it, as in peer-comparison tables).
4. **Normalizes** numbers, percentages, currency (with crore/lakh/
   million/billion scale detection), and reporting periods, while
   always preserving the original as-reported value and unit alongside
   the standardized ones.
5. **Resolves entities**: known competitor brand names (Awfis, WeWork,
   Table Space, IndiQube, etc.) are matched from table/column text;
   company-context tables default to the document's own subject company
   (detected from an ALL-CAPS "... LIMITED" pattern in the source text
   itself, never fabricated); anything else is left unresolved rather
   than guessed.
6. **Runs quality control**: percentage-range checks, unit-retention
   checks, and cross-page duplicate/conflict detection (flags cases
   where the same metric/entity/period is reported with different
   values on different pages).
7. **Loads the Silver database**: `fact_observation` (one row per
   normalized metric value, with full provenance back to
   document/page/table), plus `dim_metric`, `dim_entity`,
   `dim_geography`, `dim_date`.
8. **Exports CSVs and reports** to `data/silver/observations/` and
   `data/silver/reports/` (all observations, high-confidence only,
   needs-review only, table classification report, metric registry,
   entity registry, data quality report).

**Verified against the real 583-page Smartworks RHP**: 527/529 tables
classified as relevant, 417 observations extracted, spanning 15
distinct metrics and 5 entities (the filing company plus 4 named
competitors - Awfis, WeWork, Table Space, IndiQube - correctly
identified from a peer-comparison table). Core financial figures
(revenue, EBITDA, net profit, net worth) were spot-checked and found
consistent across the 6+ separate pages that repeat them in the source
document.

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

- Only PDF ingestion/extraction/normalization is built. CSV/Excel/JSON/
  text ingestion, analytics, hypothesis testing, insight generation,
  market gap analysis, recommendations, and Power BI export do not
  exist yet.
- `run_pipeline.py` (the unified end-to-end command) does not exist yet
  — run `scripts/run_phase1_pdf_pipeline.py` then
  `scripts/run_phase2_normalization.py` for now.
- Camelot-based table extraction is optional/deferred due to its
  Ghostscript dependency; pdfplumber is used instead and flags weak
  extractions as `needs_review` rather than silently trusting them.
- OCR fallback requires Tesseract-OCR installed separately; if it is
  not present, scanned/image-only pages are flagged `needs_review`
  instead of being OCR'd (never fabricated).
- `dim_source` (the publisher/source registry, e.g. "CBRE") is not yet
  auto-populated from PDFs — the MVP does not guess a source
  organization from a filename or Word-document author metadata, since
  that would risk misattributing the report's publisher.
- **Table classification is keyword-based, not ML/LLM-based**: it is
  auditable (every decision records which keywords matched) but not
  highly precise. In particular, the GEOGRAPHIC category catches any
  table that merely mentions a known city name (e.g. a registered-office
  address on the cover page), not only genuine city-wise breakdown
  tables — the downstream metric extractor's strict requirement for a
  matching KPI row-label correctly prevents fabricating geography-tagged
  metrics from these false positives, which is why 0 geography-tagged
  observations were extracted from this document even though 37 tables
  were classified GEOGRAPHIC.
- **Multi-row/multi-column header parsing is heuristic**: tables with
  a company name spanning several columns AND a year sub-header beneath
  it (peer-comparison tables) are handled via forward-fill +
  concatenation, which works well but can occasionally bleed a label
  one column past its true boundary in complex nested headers. Observed
  in a small number of flagged (`needs_review`) observations.
- **Entity attribution defaults to the filing company** for
  company/financial tables where no more specific entity is detected.
  This is usually correct but is a known source of false "conflicts" in
  QC when a table actually reports a subsidiary's smaller figures under
  a similar row label (e.g. "Net worth: (9.57)" vs. the parent's
  "Net worth: 500.07") — the system correctly flags these as conflicting
  rather than silently picking one, but does not (yet) recognize the
  subsidiary as a distinct entity.
- Currency scale (e.g. "₹ in Million") stated in a table's caption
  *outside* the table's own cells is not parsed — figures are preserved
  at face value as they appear in the cell.

## Next development phase

Phase 3 (analytical calculations): compute descriptive statistics,
growth rates, and comparisons across the Silver-layer observations
produced by Phase 2. Also extend document ingestion to CSV/Excel/JSON/
text file types.
