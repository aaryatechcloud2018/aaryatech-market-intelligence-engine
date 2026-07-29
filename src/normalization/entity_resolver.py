"""
Entity resolution for Phase 2.

Resolves a metric observation to a generic entity (company / competitor /
market) using two strategies, in order of confidence:

1. Keyword match against a small, known-brand list (competitors) or
   explicit document-subject context (the filing company itself).
2. Document-level default: for company/financial/operational tables in a
   single-company filing, the filing subject is a defensible default
   entity - not a fabrication, since it is literally who the document is
   about. This is recorded with a lower match_confidence and a distinct
   match_method so it is clearly distinguishable from a text-matched
   entity later.

Anything that cannot be resolved by either strategy is left unresolved
(entity_name=None) rather than guessed.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.normalization.metric_definitions import KNOWN_COMPETITOR_BRANDS

_COMPANY_DEFAULT_CATEGORIES = {
    "COMPANY", "FINANCIAL", "OPERATIONAL", "PRICING", "CUSTOMER", "GOVERNANCE",
}


@dataclass
class ResolvedEntity:
    entity_name: str | None
    entity_type: str | None  # COMPANY / COMPETITOR / MARKET
    confidence: float
    match_method: str  # keyword_match / document_subject_default / unresolved


def resolve_entity(
    table_category: str,
    row_label: str,
    column_header: str | None,
    document_subject_name: str | None,
) -> ResolvedEntity:
    """Resolve the entity a single observation should be attributed to."""
    haystack = f"{row_label} {column_header or ''}".lower()
    subject_lower = (document_subject_name or "").lower()

    for brand in KNOWN_COMPETITOR_BRANDS:
        if brand in haystack and (not subject_lower or brand not in subject_lower):
            return ResolvedEntity(
                entity_name=brand.title(), entity_type="COMPETITOR",
                confidence=0.75, match_method="keyword_match",
            )

    if table_category == "COMPETITOR":
        # Classified as competitor content, but no known brand matched -
        # do not guess which competitor this refers to.
        return ResolvedEntity(None, "COMPETITOR", 0.0, "unresolved")

    if table_category in ("MARKET", "INDUSTRY"):
        return ResolvedEntity(None, "MARKET", 0.4, "unresolved")

    if table_category in _COMPANY_DEFAULT_CATEGORIES and document_subject_name:
        return ResolvedEntity(
            entity_name=document_subject_name, entity_type="COMPANY",
            confidence=0.6, match_method="document_subject_default",
        )

    return ResolvedEntity(None, None, 0.0, "unresolved")
