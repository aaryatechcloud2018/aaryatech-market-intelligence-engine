"""
Rule-based table classification + relevance scoring.

Classifies each extracted table into one of 14 categories using keyword
matching against the table's own cell text (no LLM required - this must
work fully offline per the MVP constraint). This is a deliberately
simple, auditable classifier: every classification decision records
which keywords matched (``classification_basis``) so a human can verify
or override it later. It will not be as accurate as an LLM-based
classifier, and that tradeoff is documented rather than hidden.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

CATEGORIES = (
    "MARKET", "COMPANY", "COMPETITOR", "FINANCIAL", "OPERATIONAL",
    "GEOGRAPHIC", "CUSTOMER", "PRICING", "INDUSTRY", "RISK", "LEGAL",
    "GOVERNANCE", "OTHER", "IRRELEVANT",
)

# Categories considered core to Market Intelligence work; used to weight
# relevance scoring so MI-relevant tables surface first.
_MI_PRIORITY_CATEGORIES = {"MARKET", "COMPETITOR", "FINANCIAL", "OPERATIONAL",
                            "GEOGRAPHIC", "CUSTOMER", "PRICING", "INDUSTRY"}

# Keyword -> category. Checked in order; a table's text is scored against
# every category and the highest-scoring category wins ties broken by
# list order (so more specific categories should be listed earlier).
_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "MARKET": (
        "market size", "total addressable market", "market opportunity", "cagr",
        "market growth", "market overview", "industry size", "flexible workspace market",
        "coworking market", "demand drivers", "market penetration",
    ),
    "COMPETITOR": (
        "wework", "awfis", "tablespace", "table space", "indiqube", "91springboard",
        "cowrks", "co-wrks", "innov8", "regus", "iwg", "devx", "simpliwork", "skootr",
        "gowork", "the executive centre", "competitive landscape", "competitors", "peer comparison",
    ),
    "FINANCIAL": (
        "revenue from operations", "ebitda", "profit for the year", "profit after tax",
        "total income", "total expenses", "balance sheet", "statement of profit and loss",
        "cash flow", "total assets", "total liabilities", "net worth", "borrowings",
        "earnings per share", "restated financial",
    ),
    "OPERATIONAL": (
        "occupancy", "chargeable seats", "seating capacity", "number of centres",
        "number of centers", "area under management", "leasable area", "operational metrics",
        "capacity utilisation", "capacity utilization",
    ),
    "GEOGRAPHIC": (
        "city-wise", "citywise", "state-wise", "region-wise", "geographical presence",
        "presence across", "delhi", "mumbai", "bengaluru", "bangalore", "pune", "hyderabad",
        "chennai", "kolkata", "gurugram", "noida",
    ),
    "CUSTOMER": (
        "client", "customer", "top 10 clients", "top ten clients", "client concentration",
        "client retention", "customer segments",
    ),
    "PRICING": (
        "price per seat", "average price", "pricing", "arpu", "arr per seat", "rate card",
    ),
    "INDUSTRY": (
        "industry overview", "industry structure", "regulatory framework", "sector overview",
        "porter", "industry analysis",
    ),
    "RISK": (
        "risk factor", "risks relating", "internal risk", "external risk", "material risk",
    ),
    "LEGAL": (
        "litigation", "legal proceedings", "material contracts", "regulatory approvals",
        "show cause notice", "criminal proceeding", "civil proceeding",
    ),
    "GOVERNANCE": (
        "board of directors", "committees of our board", "corporate governance",
        "audit committee", "shareholding pattern", "key managerial personnel",
    ),
    "COMPANY": (
        "our company", "corporate identity number", "registered office", "incorporation",
        "subsidiaries", "our business", "company overview",
    ),
}

# Terms that suggest a table is boilerplate/definitional and NOT useful for
# Market Intelligence analysis, even if it superficially matches a keyword
# above (e.g. a "Definitions" table that happens to mention "market").
_IRRELEVANT_SIGNALS = (
    "means", "shall mean", "refers to", "the term", "abbreviation",
)


def _table_to_text(rows: list[list[Any]]) -> str:
    parts = []
    for row in rows:
        for cell in row:
            if cell:
                parts.append(str(cell))
    return " \n ".join(parts).lower()


@dataclass
class ClassificationResult:
    category: str
    relevance_score: float
    confidence: float
    basis: str  # human-readable explanation


def classify_table(rows: list[list[Any]]) -> ClassificationResult:
    """
    Classify a single extracted table (list of row lists).

    Scoring is simple term-frequency keyword matching per category. The
    winning category's match count relative to total matches across all
    categories becomes the ``confidence``. ``relevance_score`` additionally
    weights toward categories useful for Market Intelligence and penalizes
    tables that look like glossary/definition boilerplate.
    """
    if not rows:
        return ClassificationResult("IRRELEVANT", 0.0, 1.0, "empty table")

    text = _table_to_text(rows)
    if not text.strip():
        return ClassificationResult("IRRELEVANT", 0.0, 1.0, "no text content")

    scores: dict[str, list[str]] = {cat: [] for cat in _CATEGORY_KEYWORDS}
    for category, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[category].append(kw)

    total_matches = sum(len(v) for v in scores.values())

    if total_matches == 0:
        # Definition-style two-column glossary tables are extremely common
        # in RHPs and carry no quantitative MI value.
        is_glossary = any(sig in text for sig in _IRRELEVANT_SIGNALS)
        category = "IRRELEVANT" if is_glossary else "OTHER"
        return ClassificationResult(category, 0.05, 0.5, "no category keywords matched")

    best_category = max(scores, key=lambda c: len(scores[c]))
    best_matches = scores[best_category]
    confidence = round(len(best_matches) / total_matches, 3)
    numeric_cell_ratio = _numeric_cell_ratio(rows)

    # A weak keyword match (e.g. "our Company" appearing inside a
    # definition's prose) on a table that is otherwise all-text,
    # glossary-style prose is very likely a defined-terms table, not
    # genuine MI content - override rather than trust the weak match.
    is_glossary_signal = any(sig in text for sig in _IRRELEVANT_SIGNALS)
    if is_glossary_signal and len(best_matches) <= 1 and numeric_cell_ratio < 0.15:
        return ClassificationResult(
            "IRRELEVANT", 0.05, 0.6,
            f"glossary/definition-style table (weak match '{best_matches[0]}' overridden)",
        )

    # Relevance: prioritize MI-relevant categories; discount glossary-style
    # tables even if they weakly matched a keyword.
    base_relevance = 0.85 if best_category in _MI_PRIORITY_CATEGORIES else 0.35
    if best_category in ("RISK", "LEGAL", "GOVERNANCE"):
        base_relevance = 0.2
    if is_glossary_signal and len(best_matches) <= 1:
        base_relevance *= 0.5

    # Tables with more numeric-looking cells are more likely to carry
    # extractable KPIs, so nudge relevance up for numeric-heavy tables.
    relevance_score = round(min(1.0, base_relevance * (0.6 + 0.4 * numeric_cell_ratio)), 3)

    basis = f"matched: {', '.join(sorted(set(best_matches)))}"
    return ClassificationResult(best_category, relevance_score, confidence, basis)


_NUMERIC_CELL_RE = re.compile(r"\d")


def _numeric_cell_ratio(rows: list[list[Any]]) -> float:
    total = 0
    numeric = 0
    for row in rows:
        for cell in row:
            if cell in (None, ""):
                continue
            total += 1
            if _NUMERIC_CELL_RE.search(str(cell)):
                numeric += 1
    return numeric / total if total else 0.0
