"""
scale_downstream.py -- FINAL DEMONSTRATION RUN ONLY.

Builds the scenario library, application x behavior bridge, and behavior x
outcome dataset from the FULL mapping table (behavioral_mappings.csv), which
covers all 6,749 evidence items with mapping_source provenance. This is
separate from scenario_mapping.py / application_behavior_builder.py /
behavior_outcome_builder.py, which remain correctly scoped to
human-approved-only evidence for the standard, ongoing pipeline.
"""
import uuid
import pandas as pd

SCENARIO_COLUMNS = [
    "scenario_id", "scenario_name", "mechanism_id", "mechanism_name",
    "observable_evidence", "journey_stage", "alternative_explanation",
    "information_gap", "outcome_association", "mapping_source",
]
BRIDGE_COLUMNS = ["application_id", "mechanism_id", "mechanism_name", "mapping_source", "mapping_confidence"]
OUTCOME_COLUMNS = [
    "application_id", "mechanism_id", "mechanism_name", "mapping_source", "research_split",
    "final_disposition", "job_family", "client_account_id", "recruiter_id",
]
ALLOWED_OUTCOME_SPLITS = {"discovery", "hypothesis_generation"}
PROTECTED_SPLIT = "held_out_test"
LOW_CONFIDENCE_THRESHOLD = 0.5


def build_final_scenario_library(mappings_df: pd.DataFrame, applications_df: pd.DataFrame) -> pd.DataFrame:
    supported = mappings_df[mappings_df.mechanism_id.astype(str).str.len() > 0].copy()
    app_lookup = applications_df.set_index("application_id")

    rows = []
    for _, m in supported.iterrows():
        alt_reason = str(m.get("alternative_reason", "") or "")
        alternative_explanation = alt_reason if alt_reason else "Not identified from current evidence."

        gap_notes = []
        if m.mapping_source == "MODEL_APPLIED_FROM_CALIBRATED_FRAMEWORK":
            gap_notes.append("Not human-reviewed -- model-applied from the calibrated framework.")
        if str(m.get("alternative_mechanism_id", "") or ""):
            gap_notes.append(f"Evidence also plausibly supports an alternative mechanism "
                              f"({m.alternative_mechanism_id}); not fully disambiguated.")
        try:
            conf = float(m.get("mapping_confidence", 0) or 0)
        except (TypeError, ValueError):
            conf = 0.0
        if conf < LOW_CONFIDENCE_THRESHOLD:
            gap_notes.append(f"Mapping confidence ({conf:.2f}) below moderate threshold ({LOW_CONFIDENCE_THRESHOLD}).")
        information_gap = " ".join(gap_notes) if gap_notes else "None identified from current evidence."

        outcome_association = "Unknown split -- excluded"
        app_id = m.application_id
        if app_id in app_lookup.index:
            split = app_lookup.loc[app_id].research_split
            if split == PROTECTED_SPLIT:
                outcome_association = "EXCLUDED -- held_out_test is protected."
            elif split in ALLOWED_OUTCOME_SPLITS:
                disp = app_lookup.loc[app_id].final_disposition
                outcome_association = f"Single observation only: final_disposition={disp}. Descriptive, not a statistical association."

        rows.append({
            "scenario_id": f"SCN-{uuid.uuid4().hex[:12]}",
            "scenario_name": f"{m.mechanism_name} \u2014 {m.journey_stage}",
            "mechanism_id": m.mechanism_id, "mechanism_name": m.mechanism_name,
            "observable_evidence": m.evidence_span, "journey_stage": m.journey_stage,
            "alternative_explanation": alternative_explanation, "information_gap": information_gap,
            "outcome_association": outcome_association, "mapping_source": m.mapping_source,
        })
    return pd.DataFrame(rows, columns=SCENARIO_COLUMNS)


def build_final_bridge(mappings_df: pd.DataFrame, applications_df: pd.DataFrame) -> pd.DataFrame:
    supported = mappings_df[mappings_df.mechanism_id.astype(str).str.len() > 0].copy()
    app_split = applications_df.set_index("application_id")["research_split"]
    supported = supported[supported.application_id.map(app_split) != PROTECTED_SPLIT]

    supported["_source_rank"] = supported.mapping_source.map(
        {"HUMAN_REVIEWED": 0, "MODEL_APPLIED_FROM_CALIBRATED_FRAMEWORK": 1}
    )
    supported = supported.sort_values("_source_rank").drop_duplicates(
        subset=["application_id", "mechanism_id"], keep="first"
    )
    return supported[BRIDGE_COLUMNS].reset_index(drop=True)


def build_final_behavior_outcome(bridge_df: pd.DataFrame, applications_df: pd.DataFrame) -> pd.DataFrame:
    apps = applications_df[applications_df.research_split.isin(ALLOWED_OUTCOME_SPLITS)][
        ["application_id", "research_split", "final_disposition", "job_family", "client_account_id", "recruiter_id"]
    ]
    merged = bridge_df.merge(apps, on="application_id", how="inner")
    result = merged[OUTCOME_COLUMNS].reset_index(drop=True)
    assert (result.research_split == PROTECTED_SPLIT).sum() == 0, "held_out_test leaked into behavior_outcome_dataset"
    return result
