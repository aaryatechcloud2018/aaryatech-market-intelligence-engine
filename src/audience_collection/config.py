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

# Legacy (Stage 2 V1, Oct-Dec 2024 window) flat file paths. Left in place,
# untouched, for continuity with any local run that already used them --
# NOT used by the current (Feb-Jul 2026) collection, which uses windowed,
# per-platform-folder paths instead (see raw_path_for()/cleaned_path_for()
# below). See data/audience/README.md for the full explanation.
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

# v2 manual-review CSVs for this Feb-Jul 2026 Google Play + Reddit pass
# (exact filenames as requested -- not derived from the window dates, since
# a fixed, memorable name is easier to find in Excel/Explorer than a
# date-stamped one).
GOOGLE_PLAY_REVIEW_FILE = HUMAN_REVIEW_DIR / "wealthsimple_google_play_feb_jul_2026_manual_review.csv"
REDDIT_REVIEW_FILE = HUMAN_REVIEW_DIR / "wealthsimple_reddit_feb_jul_2026_manual_review.csv"
COMBINED_REVIEW_FILE = HUMAN_REVIEW_DIR / "wealthsimple_combined_feb_jul_2026_manual_review.csv"

# --- Target brand/product --------------------------------------------------
BRAND = "Wealthsimple"
DEFAULT_PRODUCT = "Wealthsimple App (general)"

# --- Collection window -----------------------------------------------------
# Research window requested for this pass. Real, public business context for
# this exact period (via web search, 2026-08-23): Wealthsimple reported Q2
# 2026 (Apr-Jun) net inflows of ~$17B driven by chequing/spending products,
# with new chequing account openings outpacing new investment account
# openings for the first time -- a genuine shift in what the audience is
# adopting, reported July 29, 2026 (source: newsroom.wealthsimple.com).
COLLECTION_WINDOW_START = date(2026, 2, 1)
COLLECTION_WINDOW_END = date(2026, 7, 31)
CAMPAIGN_OR_EVENT = (
    "Chequing/spending product growth surge -- Q2 2026 net inflows ~$17B, "
    "new chequing account openings outpaced new investment accounts for the "
    "first time (reported 2026-07-29)"
)


def _slug(d: date) -> str:
    return d.isoformat()


def windowed_filename(platform: str, window_start: date, window_end: date, suffix: str) -> str:
    """e.g. wealthsimple_google_play_2026-02-01_to_2026-07-31_raw.csv"""
    return f"wealthsimple_{platform}_{_slug(window_start)}_to_{_slug(window_end)}_{suffix}.csv"


def raw_path_for(platform: str, window_start: date = None, window_end: date = None) -> Path:
    """Per-platform-folder, window-stamped raw file path, e.g.
    data/audience/raw/google_play/wealthsimple_google_play_2026-02-01_to_2026-07-31_raw.csv
    Never overwritten across runs of the SAME window (append-only, see
    collectors/base.py::append_new_raw_rows); a different window gets a
    different file, by design, so research periods stay separately auditable."""
    window_start = window_start or COLLECTION_WINDOW_START
    window_end = window_end or COLLECTION_WINDOW_END
    return RAW_DIR / platform / windowed_filename(platform, window_start, window_end, "raw")


def cleaned_path_for(platform: str, window_start: date = None, window_end: date = None) -> Path:
    window_start = window_start or COLLECTION_WINDOW_START
    window_end = window_end or COLLECTION_WINDOW_END
    return PROCESSED_DIR / platform / windowed_filename(platform, window_start, window_end, "cleaned")


# --- Reddit ------------------------------------------------------------
# Named subreddits to search explicitly, PLUS a sitewide "all" search (see
# reddit_collector.py) so relevant discussion in subreddits not listed here
# is not blindly excluded.
REDDIT_SUBREDDITS = ["Wealthsimple", "PersonalFinanceCanada", "CanadianInvestor"]
REDDIT_SITEWIDE_SUBREDDIT = "all"

# Multiple collection/search terms -- NOT behavioral classification, just
# ways to find on-topic discussion (per the task's Reddit Search Relevance
# section). Deliberately excludes bare single words that would over-match
# (e.g. just "fees" or "support").
REDDIT_SEARCH_QUERIES = [
    "Wealthsimple",
    "Wealthsimple Trade",
    "Wealthsimple app",
    "Wealthsimple Cash",
    "Wealthsimple Chequing",
    "Wealthsimple investing",
    "Wealthsimple transfer",
    "Wealthsimple fees",
    "Wealthsimple support",
    "Wealthsimple account",
    "Wealthsimple vs Questrade",
    "switching to Wealthsimple",
    "leaving Wealthsimple",
]

REDDIT_USER_AGENT = "AaryatechAudienceResearch/1.0 (contact: research@aaryatech.internal)"
# Reddit's public, unauthenticated .json endpoints now reliably return
# "403 Client Error: Blocked" for scripted requests (see reddit_collector.py
# docstring for the full explanation) -- OAuth via PRAW is REQUIRED, not just
# preferred. Get a free "script" app at https://www.reddit.com/prefs/apps
# and set these in your local .env file (see .env.example).
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")

# --- Google Play ---------------------------------------------------------
GOOGLE_PLAY_APP_ID = "com.wealthsimple.trade"
GOOGLE_PLAY_COUNTRY = "ca"
GOOGLE_PLAY_LANG = "en"
# Safety valve only, not a real target cap -- per this task's instruction not
# to artificially stop early, this is set far above any plausible review
# volume for one app in a 6-month window. Paging itself stops the moment
# review dates page past window_start (see google_play_collector.py).
GOOGLE_PLAY_MAX_FETCH = 50000

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
