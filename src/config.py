"""
Central configuration for the Aaryatech Market Intelligence Engine.

All file-system paths used by the pipeline are defined here so that
every module (ingestion, extraction, normalization, analytics, etc.)
refers to a single source of truth. Nothing else in the codebase
should hard-code a path.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load variables from a .env file if one exists (never required).
load_dotenv()

# --- Project root -----------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --- Input directories (users drop their raw files here) --------------
DATA_DIR = PROJECT_ROOT / "data"
INPUT_DIR = DATA_DIR / "input"
INPUT_PDF_DIR = INPUT_DIR / "pdf"
INPUT_CSV_DIR = INPUT_DIR / "csv"
INPUT_EXCEL_DIR = INPUT_DIR / "excel"
INPUT_JSON_DIR = INPUT_DIR / "json"
INPUT_TEXT_DIR = INPUT_DIR / "text"

# --- Layered data lake (Bronze -> Silver -> Gold) ----------------------
BRONZE_DIR = DATA_DIR / "bronze"
BRONZE_DOCUMENTS_DIR = BRONZE_DIR / "documents"   # raw extracted text/pages
BRONZE_TABLES_DIR = BRONZE_DIR / "tables"         # raw extracted tables
BRONZE_STRUCTURED_DIR = BRONZE_DIR / "structured"  # raw CSV/Excel/JSON copies

SILVER_DIR = DATA_DIR / "silver"                  # cleaned/standardized data

GOLD_DIR = DATA_DIR / "gold"
GOLD_POWERBI_DIR = GOLD_DIR / "powerbi"           # Power BI-ready CSV exports

# --- Database -----------------------------------------------------------
DATABASE_DIR = PROJECT_ROOT / "database"
DEFAULT_DATABASE_PATH = DATABASE_DIR / "market_intelligence.db"
DATABASE_PATH = Path(os.getenv("DATABASE_PATH") or DEFAULT_DATABASE_PATH)

# --- Logging --------------------------------------------------------------
LOG_DIR = PROJECT_ROOT / "logs"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# --- Supported input file extensions ------------------------------------
SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".csv": "csv",
    ".xlsx": "excel",
    ".xls": "excel",
    ".json": "json",
    ".txt": "text",
}

ALL_DIRS = [
    DATA_DIR,
    INPUT_DIR,
    INPUT_PDF_DIR,
    INPUT_CSV_DIR,
    INPUT_EXCEL_DIR,
    INPUT_JSON_DIR,
    INPUT_TEXT_DIR,
    BRONZE_DIR,
    BRONZE_DOCUMENTS_DIR,
    BRONZE_TABLES_DIR,
    BRONZE_STRUCTURED_DIR,
    SILVER_DIR,
    GOLD_DIR,
    GOLD_POWERBI_DIR,
    DATABASE_DIR,
    LOG_DIR,
]


def ensure_directories() -> None:
    """Create every directory the pipeline depends on, if missing."""
    for directory in ALL_DIRS:
        directory.mkdir(parents=True, exist_ok=True)
