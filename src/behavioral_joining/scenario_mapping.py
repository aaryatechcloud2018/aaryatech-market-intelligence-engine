"""
scenario_mapping.py -- Stage 6: Client Scenario Generation.

Input: ONLY human-approved (APPROVE/EDIT) behavioral mechanism mappings from
mechanism_human_review.csv, where the effective mechanism is a real BM-XXX
(NO_SUPPORTED_MECHANISM, PENDING, and REJECT rows are never used).

A scenario is NOT a new behavioral mechanism -- it always traces back to one or
more frozen BM-XXX mechanisms via mechanism_id. This module never fabricates
information: every field is either copied directly from already-approved,
traceable source data, or explicitly marked as an information gap.

MVP scoping note: this generates one scenario record per approved
evidence-mechanism mapping. Clustering multiple evidence instances into a single
named, recurring scenario (e.g. "Current-Employment Attachment") is a future
human-curation step -- automating that grouping now would mean inventing a
category boundary that isn't in the data, so it is deliberately left as a
distinguishable next step, not done here.

HARD SAFEGUARD: this module has no write path to
data/behavioral_joining/reference/behavioral_mechanisms.json. It only ever
calls mechanism_library.load_mechanism_library(), which is read-only.
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import uuid
import pandas as pd

from .mechanism_library import load_mechanism_library

SCENARIO_COLUMNS = [
    "scenario_id", "scenario_name", "mechanism_id", "mechanism_name",
    "observable_evidence", "journey_stage", "alternative_explanation",
    "information_gap", "outcome_association",
]

# Splits a scenario's outcome_association note is allowed to reference.
# held_out_test is never permitted here, defensively, even though evidence
# extraction structurally only ever touches the discovery split today.
ALLOWED_OUTCOME_SPLITS = {"discovery", "hypothesis_generation"}

LOW_CONFIDENCE_THRESHOLD = 0.5


def get_human_approved_mappings(mapping_review_df: pd.DataFrame) -> pd.DataFrame:
    """APPROVE/EDIT rows only, with a real (non-empty) effective mechanism_id.
    Excludes PENDING, REJECT, and NO_SUPPORTED_MECHANISM rows entirely."""
    if len(mapping_review_df) == 0:
        return mapping_review_df.copy()
    df = mapping_review_df[mapping_review_df.human_mapping_decision.isin(["APPROVE", "EDIT"])].copy()
    df["effective_mechanism_id"] = df["human_selected_mechanism"].where(
        df["human_selected_mechanism"].astype(str).str.len() > 0, df["mechanism_id"]
    )
    return df[df["effective_mechanism_id"].astype(str).str.len() > 0]


def mechanism_name_lookup() -> dict:
    lib = load_mechanism_library()  # read-only; never writes
    if lib.status != "LOADED":
        return {}
    return {m["Pattern_ID"]: m["Pattern_Name"] for m in lib.mechanisms}


def infer_journey_stage(application_id: str, evidence_timestamp, stage_events_df: pd.DataFrame) -> str:
    """Last recorded stage_name at or before the evidence timestamp for this
    application. Returns 'unknown' if no stage event can be traced -- never guessed."""
    sub = stage_events_df[stage_events_df.application_id == application_id].copy()
    if len(sub) == 0:
        return "unknown"
    sub["stage_timestamp"] = pd.to_datetime(sub["stage_timestamp"])
    sub = sub[sub.stage_timestamp <= evidence_timestamp].sort_values("stage_timestamp")
    if len(sub) == 0:
        return "unknown"
    return sub.iloc[-1].stage_name


def build_scenario_library(mapping_review_df: pd.DataFrame,
                            evidence_candidates_df: pd.DataFrame,
                            stage_events_df: pd.DataFrame,
                            applications_df: pd.DataFrame) -> pd.DataFrame:
    approved = get_human_approved_mappings(mapping_review_df)
    if len(approved) == 0:
        return pd.DataFrame(columns=SCENARIO_COLUMNS)

    mech_names = mechanism_name_lookup()
    ev_lookup = evidence_candidates_df.set_index("evidence_id")
    app_lookup = applications_df.set_index("application_id")

    rows = []
    for _, m in approved.iterrows():
        if m.evidence_id not in ev_lookup.index:
            continue  # cannot fabricate a scenario from evidence we can't trace
        ev = ev_lookup.loc[m.evidence_id]
        app_id = m.application_id
        mech_id = m.effective_mechanism_id
        mech_name = mech_names.get(mech_id, m.mechanism_name if pd.notna(m.mechanism_name) else "")

        ev_timestamp = pd.to_datetime(ev.timestamp)
        journey_stage = infer_journey_stage(app_id, ev_timestamp, stage_events_df)

        scenario_name = f"{mech_name} \u2014 {ev.evidence_category}" if mech_name else f"Unnamed mechanism ({mech_id}) \u2014 {ev.evidence_category}"

        alt_reason = str(m.get("alternative_reason", "") or "")
        alternative_explanation = alt_reason if alt_reason else "Not identified from current evidence."

        gap_notes = []
        if str(m.get("alternative_mechanism_id", "") or ""):
            alt_id = m.alternative_mechanism_id
            alt_name = mech_names.get(alt_id, alt_id)
            gap_notes.append(f"Evidence also plausibly supports {alt_name} ({alt_id}); primary mechanism not fully disambiguated.")
        try:
            conf = float(m.get("mapping_confidence", 0) or 0)
        except (TypeError, ValueError):
            conf = 0.0
        if conf < LOW_CONFIDENCE_THRESHOLD:
            gap_notes.append(f"Mapping confidence ({conf:.2f}) is below the moderate threshold ({LOW_CONFIDENCE_THRESHOLD}); additional evidence recommended before relying on this scenario.")
        information_gap = " ".join(gap_notes) if gap_notes else "None identified from current evidence."

        outcome_association = "Unknown split -- excluded"
        if app_id in app_lookup.index:
            split = app_lookup.loc[app_id].research_split
            if split == "held_out_test":
                outcome_association = "EXCLUDED -- held_out_test is protected and never referenced here."
            elif split in ALLOWED_OUTCOME_SPLITS:
                disp = app_lookup.loc[app_id].final_disposition
                outcome_association = f"Single observation only: final_disposition={disp}. Descriptive, not a statistical association."

        rows.append({
            "scenario_id": f"SCN-{uuid.uuid4().hex[:12]}",
            "scenario_name": scenario_name,
            "mechanism_id": mech_id,
            "mechanism_name": mech_name,
            "observable_evidence": ev.evidence_span,
            "journey_stage": journey_stage,
            "alternative_explanation": alternative_explanation,
            "information_gap": information_gap,
            "outcome_association": outcome_association,
        })

    return pd.DataFrame(rows, columns=SCENARIO_COLUMNS)
