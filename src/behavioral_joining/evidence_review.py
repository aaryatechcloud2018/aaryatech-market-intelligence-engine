"""
evidence_review.py

Human-in-the-loop review workflow for AI-proposed evidence candidates.

Hard rule: behavioral_evidence_candidates.csv (the AI's original proposals) is NEVER
modified by this module. All review actions are recorded as NEW rows/updates in
behavioral_evidence_review.csv, which preserves the original evidence alongside the
human decision. Nothing in this module auto-approves anything -- every evidence row
starts and stays "pending" until a human analyst explicitly calls approve/reject/edit.
"""
from datetime import datetime, timezone
import pandas as pd

REVIEW_COLUMNS = [
    "evidence_id", "application_id",
    "original_evidence_span", "original_evidence_category", "original_evidence_description",
    "original_evidence_strength",
    "review_decision",           # pending / approved / rejected / edited
    "edited_evidence_category", "edited_evidence_description", "edited_evidence_strength",
    "reviewer", "review_timestamp", "reviewer_notes",
]


def initialize_review_file(evidence_candidates: pd.DataFrame) -> pd.DataFrame:
    """Creates the review ledger with one pending row per AI-proposed evidence item.
    This does NOT approve anything -- 'pending' is the only status set here."""
    rows = []
    for _, r in evidence_candidates.iterrows():
        rows.append({
            "evidence_id": r.evidence_id,
            "application_id": r.application_id,
            "original_evidence_span": r.evidence_span,
            "original_evidence_category": r.evidence_category,
            "original_evidence_description": r.evidence_description,
            "original_evidence_strength": r.evidence_strength,
            "review_decision": "pending",
            "edited_evidence_category": "",
            "edited_evidence_description": "",
            "edited_evidence_strength": "",
            "reviewer": "",
            "review_timestamp": "",
            "reviewer_notes": "",
        })
    return pd.DataFrame(rows, columns=REVIEW_COLUMNS)


def _now():
    return datetime.now(timezone.utc).isoformat()


def approve_evidence(review_df: pd.DataFrame, evidence_id: str, reviewer: str, notes: str = "") -> pd.DataFrame:
    return _update_review(review_df, evidence_id, decision="approved", reviewer=reviewer, notes=notes)


def reject_evidence(review_df: pd.DataFrame, evidence_id: str, reviewer: str, notes: str = "") -> pd.DataFrame:
    return _update_review(review_df, evidence_id, decision="rejected", reviewer=reviewer, notes=notes)


def edit_evidence(review_df: pd.DataFrame, evidence_id: str, reviewer: str, notes: str = "",
                   new_category: str = None, new_description: str = None, new_strength: str = None) -> pd.DataFrame:
    """Records a human-edited version. The ORIGINAL AI proposal columns are left
    untouched -- only the edited_* columns and review_decision are set."""
    df = review_df.copy()
    idx = df.index[df.evidence_id == evidence_id]
    if len(idx) == 0:
        raise KeyError(f"evidence_id '{evidence_id}' not found in review file")
    i = idx[0]
    if new_category is not None:
        df.at[i, "edited_evidence_category"] = new_category
    if new_description is not None:
        df.at[i, "edited_evidence_description"] = new_description
    if new_strength is not None:
        df.at[i, "edited_evidence_strength"] = new_strength
    df.at[i, "review_decision"] = "edited"
    df.at[i, "reviewer"] = reviewer
    df.at[i, "review_timestamp"] = _now()
    df.at[i, "reviewer_notes"] = notes
    return df


def _update_review(review_df: pd.DataFrame, evidence_id: str, decision: str, reviewer: str, notes: str) -> pd.DataFrame:
    df = review_df.copy()
    idx = df.index[df.evidence_id == evidence_id]
    if len(idx) == 0:
        raise KeyError(f"evidence_id '{evidence_id}' not found in review file")
    i = idx[0]
    df.at[i, "review_decision"] = decision
    df.at[i, "reviewer"] = reviewer
    df.at[i, "review_timestamp"] = _now()
    df.at[i, "reviewer_notes"] = notes
    return df


def get_approved_or_edited(review_df: pd.DataFrame) -> pd.DataFrame:
    """Only approved/edited evidence may proceed to mechanism mapping."""
    return review_df[review_df.review_decision.isin(["approved", "edited"])].copy()
