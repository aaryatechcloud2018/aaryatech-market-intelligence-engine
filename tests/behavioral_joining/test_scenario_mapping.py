import pytest
import pandas as pd
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.behavioral_joining.scenario_mapping import (
    build_scenario_library, get_human_approved_mappings, infer_journey_stage, SCENARIO_COLUMNS,
)

FROZEN_LIBRARY_PATH = Path(__file__).resolve().parents[2] / "data" / "behavioral_joining" / "reference" / "behavioral_mechanisms.json"


def _mapping_review(decision="APPROVE", mechanism_id="BM-002", human_selected="", alt_id="", alt_reason="", confidence=0.6):
    return pd.DataFrame([{
        "mapping_id": "M1", "evidence_id": "EV1", "application_id": "APP-1",
        "mechanism_id": mechanism_id, "mechanism_name": "Loss Aversion",
        "mapping_reason": "r", "supporting_context": "", "contradictory_context": "",
        "mapping_confidence": confidence, "alternative_mechanism_id": alt_id, "alternative_reason": alt_reason,
        "mapping_status": "PROPOSED", "human_mapping_decision": decision,
        "human_selected_mechanism": human_selected, "human_mapping_notes": "",
    }])


def _evidence():
    return pd.DataFrame([{
        "evidence_id": "EV1", "application_id": "APP-1", "log_id": "L1", "timestamp": "2024-03-05",
        "source_type": "candidate_message", "direction": "candidate_facing",
        "evidence_span": "I withdraw due to job security concerns", "evidence_category": "withdrawal_language",
        "evidence_description": "", "context_before": "", "context_after": "",
        "response_latency_hours": 2, "extractor_confidence": 0.7, "review_status": "approved", "reviewer_notes": "",
    }])


def _stages():
    return pd.DataFrame([{
        "event_id": "E1", "application_id": "APP-1", "stage_name": "offer_accepted",
        "stage_timestamp": "2024-03-01", "days_in_prior_stage": 0,
    }])


def _apps():
    return pd.DataFrame([{
        "application_id": "APP-1", "research_split": "discovery",
        "final_disposition": "withdrew_post_acceptance",
    }])


def test_get_human_approved_mappings_excludes_pending_and_reject():
    df = pd.concat([_mapping_review("PENDING"), _mapping_review("REJECT")], ignore_index=True)
    result = get_human_approved_mappings(df)
    assert len(result) == 0


def test_get_human_approved_mappings_excludes_no_supported_mechanism():
    df = _mapping_review("APPROVE", mechanism_id="")  # NO_SUPPORTED_MECHANISM shape
    result = get_human_approved_mappings(df)
    assert len(result) == 0


def test_get_human_approved_mappings_includes_approve_and_edit():
    df = pd.concat([_mapping_review("APPROVE"), _mapping_review("EDIT", human_selected="BM-005")], ignore_index=True)
    result = get_human_approved_mappings(df)
    assert len(result) == 2


def test_infer_journey_stage_finds_last_stage_at_or_before_timestamp():
    stage = infer_journey_stage("APP-1", pd.Timestamp("2024-03-05"), _stages())
    assert stage == "offer_accepted"


def test_infer_journey_stage_unknown_when_no_events():
    empty_stages = pd.DataFrame(columns=["application_id", "stage_name", "stage_timestamp"])
    stage = infer_journey_stage("APP-1", pd.Timestamp("2024-03-05"), empty_stages)
    assert stage == "unknown"


def test_build_scenario_library_empty_when_no_approved_mappings():
    empty = pd.DataFrame(columns=["mapping_id", "evidence_id", "application_id", "mechanism_id",
                                   "mechanism_name", "human_mapping_decision", "human_selected_mechanism",
                                   "alternative_mechanism_id", "alternative_reason", "mapping_confidence"])
    result = build_scenario_library(empty, _evidence(), _stages(), _apps())
    assert len(result) == 0
    assert list(result.columns) == SCENARIO_COLUMNS


def test_build_scenario_library_produces_record_traced_to_frozen_mechanism():
    result = build_scenario_library(_mapping_review(), _evidence(), _stages(), _apps())
    assert len(result) == 1
    row = result.iloc[0]
    assert row.mechanism_id == "BM-002"
    assert row.observable_evidence == "I withdraw due to job security concerns"  # exact traceable text
    assert row.journey_stage == "offer_accepted"


def test_scenario_is_not_a_new_mechanism():
    """A scenario_id is never mistaken for a mechanism_id -- distinct ID namespaces."""
    result = build_scenario_library(_mapping_review(), _evidence(), _stages(), _apps())
    assert result.iloc[0].scenario_id.startswith("SCN-")
    assert result.iloc[0].mechanism_id.startswith("BM-")


def test_information_gap_flagged_for_low_confidence():
    result = build_scenario_library(_mapping_review(confidence=0.2), _evidence(), _stages(), _apps())
    assert "confidence" in result.iloc[0].information_gap.lower()


def test_information_gap_flagged_for_alternative_mechanism():
    result = build_scenario_library(
        _mapping_review(alt_id="BM-021", alt_reason="also plausible"), _evidence(), _stages(), _apps()
    )
    assert "BM-021" in result.iloc[0].information_gap


def test_no_information_gap_when_high_confidence_and_no_alternative():
    result = build_scenario_library(_mapping_review(confidence=0.9), _evidence(), _stages(), _apps())
    assert result.iloc[0].information_gap == "None identified from current evidence."


def test_held_out_application_never_gets_outcome_association_disposition():
    apps_held_out = pd.DataFrame([{
        "application_id": "APP-1", "research_split": "held_out_test", "final_disposition": "joined_on_time",
    }])
    result = build_scenario_library(_mapping_review(), _evidence(), _stages(), apps_held_out)
    assert "EXCLUDED" in result.iloc[0].outcome_association
    assert "joined_on_time" not in result.iloc[0].outcome_association


def test_frozen_mechanism_library_hash_unchanged_after_scenario_generation():
    before = hashlib.md5(FROZEN_LIBRARY_PATH.read_bytes()).hexdigest()
    build_scenario_library(_mapping_review(), _evidence(), _stages(), _apps())
    after = hashlib.md5(FROZEN_LIBRARY_PATH.read_bytes()).hexdigest()
    assert before == after


def test_scenario_mapping_module_has_no_write_call_to_frozen_library():
    """Static check: the module source never opens the frozen library path for writing."""
    import inspect
    from src.behavioral_joining import scenario_mapping
    source = inspect.getsource(scenario_mapping)
    assert "behavioral_mechanisms.json\", \"w\"" not in source
    assert ".write(" not in source
    assert "to_json(" not in source
