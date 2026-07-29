"""
Value, unit, and period parsing/normalization.

Every function here is deterministic and rule-based (regex + lookup
tables) - no LLM involved, and nothing is invented. If a raw string
cannot be confidently parsed, the function returns None rather than
guessing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CURRENCY_SYMBOLS = {
    "₹": "INR", "rs.": "INR", "rs": "INR", "inr": "INR",
    "$": "USD", "usd": "USD", "us$": "USD",
}

# Indian and international scale words -> multiplier to base units.
_SCALE_WORDS = {
    "crore": 1e7, "crores": 1e7, "cr": 1e7, "cr.": 1e7,
    "lakh": 1e5, "lakhs": 1e5, "lac": 1e5,
    "million": 1e6, "millions": 1e6, "mn": 1e6,
    "billion": 1e9, "billions": 1e9, "bn": 1e9,
    "thousand": 1e3, "thousands": 1e3, "'000": 1e3,
}

_NUMBER_RE = re.compile(r"[-+]?\(?\d[\d,]*\.?\d*\)?")


@dataclass
class ParsedValue:
    standardized_value: float
    standardized_unit: str | None
    parse_confidence: float  # 0.0 - 1.0


def parse_numeric_value(raw: str, table_default_unit: str | None = None) -> ParsedValue | None:
    """
    Parse a raw table cell into a standardized numeric value + unit.

    Handles: thousands separators, parenthesized negatives (accounting
    convention), percentages, currency symbols/codes, and Indian/
    international scale words (crore, lakh, million, billion).

    Returns None if the cell does not look like a numeric value at all
    (e.g. free text, "N/A", "-", blank) - callers must not fabricate a
    value in that case.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text in {"-", "--", "—", "N/A", "NA", "n/a", "Nil", "NIL"}:
        return None

    lower = text.lower()

    number_match = _NUMBER_RE.search(text)
    if not number_match:
        return None

    number_str = number_match.group()
    is_negative = number_str.startswith("(") and number_str.endswith(")")
    cleaned = number_str.strip("()").replace(",", "")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    if is_negative:
        value = -value

    confidence = 1.0

    # Percentage
    if "%" in text:
        return ParsedValue(standardized_value=value, standardized_unit="%", parse_confidence=confidence)

    # Currency detection
    currency = None
    for symbol, code in _CURRENCY_SYMBOLS.items():
        if symbol in lower:
            currency = code
            break

    # Scale word detection (applies a multiplier)
    scale_multiplier = 1.0
    for word, multiplier in _SCALE_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", lower):
            scale_multiplier = multiplier
            break
    else:
        confidence = 0.9 if currency else confidence  # currency without explicit scale is slightly less certain

    if currency:
        standardized_value = value * scale_multiplier
        return ParsedValue(standardized_value=standardized_value, standardized_unit=currency, parse_confidence=confidence)

    if table_default_unit:
        standardized_value = value * scale_multiplier
        return ParsedValue(standardized_value=standardized_value, standardized_unit=table_default_unit, parse_confidence=confidence)

    # Plain number, no unit context at all - still usable, lower confidence.
    return ParsedValue(standardized_value=value, standardized_unit=None, parse_confidence=0.7)


_YEAR_RE = re.compile(r"(19|20)\d{2}")
_FY_RE = re.compile(r"\bFY\s*'?(\d{2,4})\b", re.IGNORECASE)
_QUARTER_RE = re.compile(r"\bQ([1-4])\b", re.IGNORECASE)


@dataclass
class ParsedPeriod:
    period_label: str
    year: int
    quarter: int | None
    period_type: str  # annual / quarterly / fiscal_year


def detect_period(text: str | None) -> ParsedPeriod | None:
    """
    Detect a reporting period from header/context text, e.g.
    "Fiscal 2025", "FY25", "For the year ended March 31, 2025", "Q1 2025".

    Returns None if no plausible year can be found - periods are never
    guessed from context alone.
    """
    if not text:
        return None
    text = str(text)

    quarter_match = _QUARTER_RE.search(text)
    fy_match = _FY_RE.search(text)
    year_match = _YEAR_RE.search(text)

    year = None
    if fy_match:
        raw_year = fy_match.group(1)
        year = int(raw_year) if len(raw_year) == 4 else 2000 + int(raw_year)
    elif year_match:
        year = int(year_match.group())

    if year is None:
        return None
    if year < 1990 or year > 2035:
        return None  # implausible year - do not fabricate a period

    if quarter_match:
        q = int(quarter_match.group(1))
        return ParsedPeriod(period_label=f"Q{q} FY{year}", year=year, quarter=q, period_type="quarterly")

    if fy_match or re.search(r"fiscal|year ended|financial year", text, re.IGNORECASE):
        return ParsedPeriod(period_label=f"FY{year}", year=year, quarter=None, period_type="fiscal_year")

    return ParsedPeriod(period_label=str(year), year=year, quarter=None, period_type="annual")
