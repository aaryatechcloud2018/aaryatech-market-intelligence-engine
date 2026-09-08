"""
mechanism_mapping_review.py

Human-in-the-loop review workflow for AI-proposed mechanism mappings. Mirrors
evidence_review.py's pattern: mechanism_mapping_candidates.csv (AI originals) is
never modified; all decisions live in mechanism_mapping_review.csv.
"""
from datetime import datetime, timezone
import pandas as pd

REVIEW_COLUMNS = [
    "mapping_id", "evidence_id", "application_id",
    "original_mechanism_id", "original_mechanism_name", "original_mapping_reason",
    "original_evidence_support_level", "original_mapping_confidence",
    "review_decision",   # pending / approved / rejected / edited
    "edited_mechanism_id", "edited_mechanism_name", "added_alternative_interpretation",
    "reviewer", "review_timestamp", "reviewer_notes",
]


def initialize_mapping_review_file(mapping_candidates: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in mapping_candidates.iterrows():
        rows.append({
            "mapping_id": r.mapping_id,
            "evidence_id": r.evidence_id,
            "application_id": r.application_id,
            "original_mechanism_id": r.mechanism_id,
            "original_mechanism_name": r.mechanism_name,
            "original_mapping_reason": r.mapping_reason,
            "original_evidence_support_level": r.evidence_support_level,
            "original_mapping_confidence": r.mapping_confidence,
            "review_decision": "pending",
            "edited_mechanism_id": "",
            "edited_mechanism_name": "",
            "added_alternative_interpretation": "",
            "reviewer": "",
            "review_timestamp": "",
            "reviewer_notes": "",
        })
    return pd.DataFrame(rows, columns=REVIEW_COLUMNS)


def _now():
    return datetime.now(timezone.utc).isoformat()


def approve_mapping(review_df, mapping_id, reviewer, notes=""):
    return _update(review_df, mapping_id, "approved", reviewer, notes)


def reject_mapping(review_df, mapping_id, reviewer, notes=""):
    return _update(review_df, mapping_id, "rejected", reviewer, notes)


def change_mechanism(review_df, mapping_id, reviewer, new_mechanism_id, new_mechanism_name, notes=""):
    df = review_df.copy()
    idx = df.index[df.mapping_id == mapping_id]
    if len(idx) == 0:
        raise KeyError(f"mapping_id '{mapping_id}' not found")
    i = idx[0]
    df.at[i, "edited_mechanism_id"] = new_mechanism_id
    df.at[i, "edited_mechanism_name"] = new_mechanism_name
    df.at[i, "review_decision"] = "edited"
    df.at[i, "reviewer"] = reviewer
    df.at[i, "review_timestamp"] = _now()
    df.at[i, "reviewer_notes"] = notes
    return df


def add_alternative_interpretation(review_df, mapping_id, reviewer, alternative_text, notes=""):
    df = review_df.copy()
    idx = df.index[df.mapping_id == mapping_id]
    if len(idx) == 0:
        raise KeyError(f"mapping_id '{mapping_id}' not found")
    i = idx[0]
    df.at[i, "added_alternative_interpretation"] = alternative_text
    df.at[i, "reviewer"] = reviewer
    df.at[i, "review_timestamp"] = _now()
    if notes:
        df.at[i, "reviewer_notes"] = notes
    return df


def _update(review_df, mapping_id, decision, reviewer, notes):
    df = review_df.copy()
    idx = df.index[df.mapping_id == mapping_id]
    if len(idx) == 0:
        raise KeyError(f"mapping_id '{mapping_id}' not found")
    i = idx[0]
    df.at[i, "review_decision"] = decision
    df.at[i, "reviewer"] = reviewer
    df.at[i, "review_timestamp"] = _now()
    df.at[i, "reviewer_notes"] = notes
    return df


def get_approved_or_edited_mappings(review_df: pd.DataFrame) -> pd.DataFrame:
    """Only approved/edited mappings can enter formal behavioral analysis."""
    return review_df[review_df.review_decision.isin(["approved", "edited"])].copy()
