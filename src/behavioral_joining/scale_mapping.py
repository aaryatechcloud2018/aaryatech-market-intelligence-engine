"""
scale_mapping.py -- FINAL DEMONSTRATION RUN ONLY.

Applies the existing calibrated ContextAwareMechanismMapperBackend to ALL
discovery-split evidence, not just the 275-row human-reviewed sample.

Every output row carries mapping_source:
  HUMAN_REVIEWED                     -- one of the 275 rows a person actually decided
  MODEL_APPLIED_FROM_CALIBRATED_FRAMEWORK -- engine output, never human-checked

MODEL_APPLIED rows are NEVER relabeled HUMAN_APPROVED anywhere downstream.
NO_SUPPORTED_MECHANISM remains a valid, common outcome for both provenances.
"""
from __future__ import annotations
import pandas as pd

from .mechanism_library import load_mechanism_library
from .mechanism_mapping import ContextAwareMechanismMapperBackend

FULL_MAPPING_COLUMNS = [
    "application_id", "evidence_id", "evidence_span", "journey_stage",
    "mechanism_id", "mechanism_name", "mapping_reason", "mapping_source",
    "mapping_confidence", "alternative_mechanism_id", "alternative_reason",
    "information_gap", "research_split",
]


def build_full_mapping_table(evidence_candidates_df: pd.DataFrame,
                              human_reviewed_mapping_df: pd.DataFrame,
                              stage_events_df: pd.DataFrame,
                              applications_df: pd.DataFrame) -> pd.DataFrame:
    from .scenario_mapping import infer_journey_stage, mechanism_name_lookup

    lib = load_mechanism_library()
    backend = ContextAwareMechanismMapperBackend()
    mech_names = mechanism_name_lookup()
    app_split = applications_df.set_index("application_id")["research_split"]

    human_reviewed_ids = set(human_reviewed_mapping_df.evidence_id)
    human_by_ev = human_reviewed_mapping_df.set_index("evidence_id")

    rows = []
    for _, ev in evidence_candidates_df.iterrows():
        ev_id = ev.evidence_id
        app_id = ev.application_id
        split = app_split.get(app_id, "unknown")
        ts = pd.to_datetime(ev.timestamp)
        journey_stage = infer_journey_stage(app_id, ts, stage_events_df)

        if ev_id in human_reviewed_ids:
            h = human_by_ev.loc[ev_id]
            mech_id = h.mechanism_id if str(h.mechanism_id) else ""
            mech_name = h.mechanism_name if mech_id else ""
            rows.append({
                "application_id": app_id, "evidence_id": ev_id, "evidence_span": ev.evidence_span,
                "journey_stage": journey_stage, "mechanism_id": mech_id, "mechanism_name": mech_name,
                "mapping_reason": h.mapping_reason, "mapping_source": "HUMAN_REVIEWED",
                "mapping_confidence": h.mapping_confidence,
                "alternative_mechanism_id": h.get("alternative_mechanism_id", ""),
                "alternative_reason": h.get("alternative_reason", ""),
                "information_gap": "None -- human reviewed" if mech_id else "Human reviewer found no supported mechanism",
                "research_split": split,
            })
            continue

        # MODEL_APPLIED: run the calibrated engine directly (no human gate for this
        # demonstration-scale pass -- explicitly authorized by the PM for this run only)
        row_dict = {"evidence_category": ev.evidence_category, "evidence_span": ev.evidence_span,
                    "context_before": ev.context_before, "context_after": ev.context_after,
                    "evidence_description": ev.evidence_description,
                    "human_evidence_category": ev.evidence_category}
        proposals = backend.propose(row_dict, lib.mechanisms) if lib.status == "LOADED" else []
        if not proposals:
            rows.append({
                "application_id": app_id, "evidence_id": ev_id, "evidence_span": ev.evidence_span,
                "journey_stage": journey_stage, "mechanism_id": "", "mechanism_name": "",
                "mapping_reason": "NO_SUPPORTED_MECHANISM -- no library mechanism had sufficient, "
                                   "uncontradicted contextual support for this evidence category.",
                "mapping_source": "MODEL_APPLIED_FROM_CALIBRATED_FRAMEWORK", "mapping_confidence": 0.0,
                "alternative_mechanism_id": "", "alternative_reason": "",
                "information_gap": "Not human-reviewed; model found no supported mechanism.",
                "research_split": split,
            })
        else:
            p = proposals[0]
            rows.append({
                "application_id": app_id, "evidence_id": ev_id, "evidence_span": ev.evidence_span,
                "journey_stage": journey_stage, "mechanism_id": p["mechanism_id"],
                "mechanism_name": p["mechanism_name"], "mapping_reason": p["reason"],
                "mapping_source": "MODEL_APPLIED_FROM_CALIBRATED_FRAMEWORK",
                "mapping_confidence": p["confidence"],
                "alternative_mechanism_id": p.get("alternative_mechanism_id", ""),
                "alternative_reason": p.get("alternative_reason", ""),
                "information_gap": "Not human-reviewed -- model-applied mapping from the calibrated "
                                    "framework; treat as demonstration-grade, not validated.",
                "research_split": split,
            })

    return pd.DataFrame(rows, columns=FULL_MAPPING_COLUMNS)
