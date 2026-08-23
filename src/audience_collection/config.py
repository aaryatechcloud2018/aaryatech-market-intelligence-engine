"""
Central configuration for Stage 2 audience data collection.

Deliberately separate from src/config.py (the older market-intelligence
pipeline's config) so Stage 2 never gets wired into that pipeline by
accident.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# --- Stage 2 data folders ------------------------------------------------
AUDIENCE_DIR = PROJECT_ROOT / "data" / "audience"
RAW_DIR = AUDIENCE_DIR / "raw"
PROCESSED_DIR = AUDIENCE_DIR / "processed"
HUMAN_REVIEW_DIR = AUDIENCE_DIR / "human_review"

RAW_FILES = {
    "reddit": RAW_DIR / "reddit_raw.csv",
    "google_play": RAW_DIR / "google_play_raw.csv",
    "app_store": RAW_DIR / "app_store_raw.csv",
    "youtube": RAW_DIR / "youtube_raw.csv",
}

CLEANED_FILES = {
    "reddit": PROCESSED_DIR / "reddit_cleaned.csv",
    "google_play": PROCESSED_DIR / "google_play_cleaned.csv",
    "app_store": PROCESSED_DIR / "app_store_cleaned.csv",
    "youtube": PROCESSED_DIR / "youtube_cleaned.csv",
}

MASTER_CLEANED_FILE = PROCESSED_DIR / "audience_master_cleaned.csv"
HUMAN_REVIEW_FILE = HUMAN_REVIEW_DIR / "wealthsimple_audience_manual_review.csv"

# --- Target brand/product --------------------------------------------------
BRAND = "Wealthsimple"
DEFAULT_PRODUCT = "Wealthsimple App (general)"

# --- Collection window -----------------------------------------------------
# Chosen because it covers a real, meaningful, well-documented product event
# (national launch of Margin Trading -- Wealthsimple's first lending product,
# October 2024) with enough elapsed time for organic comment volume to
# accumulate, and clear public business context (also the peak of
# Wealthsimple's FHSA-provider-of-choice positioning going into year-end).
COLLECTION_WINDOW_START = date(2024, 10, 1)
COLLECTION_WINDOW_END = date(2024, 12, 31)
CAMPAIGN_OR_EVENT = "Margin Trading national launch (Oct 2024)"

# --- Reddit ------------------------------------------------------------
REDDIT_SUBREDDITS = ["Wealthsimple", "PersonalFinanceCanada"]
REDDIT_SEARCH_QUERY = "wealthsimple"
REDDIT_USER_AGENT = "AaryatechAudienceResearch/1.0 (contact: research@aaryatech.internal)"
# Optional OAuth credentials (needed if Reddit blocks unauthenticated public
# JSON requests, which happens increasingly often). If unset, the collector
# falls back to the public .json endpoints with no login.
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")

# --- Google Play ---------------------------------------------------------
GOOGLE_PLAY_APP_ID = "com.wealthsimple.trade"
GOOGLE_PLAY_COUNTRY = "ca"
GOOGLE_PLAY_LANG = "en"

# --- Apple App Store -------------------------------------------------------
APP_STORE_APP_ID = "1403491709"  # Wealthsimple - Grow your money
APP_STORE_COUNTRY = "ca"
APP_STORE_MAX_PAGES = 10  # RSS feed serves ~50 reviews/page, most-recent first

# --- YouTube -----------------------------------------------------------
# Official Data API v3 is used automatically if YOUTUBE_API_KEY is set (also
# used to discover videos by search). Without a key, the collector falls
# back to scraping the public comment feed of the seed videos below via
# youtube_comment_downloader -- no login required, but seed videos must be
# supplied manually since search requires the API.
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_SEED_VIDEO_URLS = [
    # Candidate real, on-topic videos found via web search on 2026-08-23.
    # Verify still live / on-topic before a production run; swap freely.
    "https://www.youtube.com/watch?v=uwpFM4nm8mw",  # "My HONEST Wealthsimple Review [Pros & Cons]"
    "https://www.youtube.com/watch?v=jxfBiSTl7mc",  # "Wealthsimple for Beginners: Detailed review"
    "https://www.youtube.com/watch?v=boaRW2SlEA0",  # "5-Year Wealthsimple Review: The Good and The Bad"
]

# --- Target scale ------------------------------------------------------
TARGET_MIN_ROWS = 500
TARGET_MAX_ROWS = 2000

# --- Near-duplicate detection -----------------------------------------------
NEAR_DUPLICATE_SIMILARITY_THRESHOLD = 0.85

# --- Low-information heuristic ----------------------------------------------
LOW_INFORMATION_MIN_CHARS = 15
LOW_INFORMATION_MIN_WORDS = 3


def ensure_directories() -> None:
    """Create every Stage 2 folder, if missing. Never touches existing files."""
    for directory in (RAW_DIR, PROCESSED_DIR, HUMAN_REVIEW_DIR):
        directory.mkdir(parents=True, exist_ok=True)
