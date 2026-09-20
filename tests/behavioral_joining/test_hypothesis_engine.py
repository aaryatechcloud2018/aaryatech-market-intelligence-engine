import pytest
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.behavioral_joining.hypothesis_engine import (
    generate_hypotheses, demo_hypothesis_illustration, Hypothesis, HYPOTHESIS_STATUSES,
    ELIGIBILITY_CONFIG,
)


def _outcome_rows(mech_id="BM-001", mech_name="Status Quo Bias", n=2, split="discovery"):
    return pd.DataFrame([{
        "application_id": f"APP-{i}", "mechanism_id": mech_id, "mechanism_name": mech_name,
        "research_split": split, "final_disposition": "withdrew_post_acceptance",
        "job_family": "IT/Technology", "client_account_id": "CLI-001", "recruiter_id": "REC-001",
    } for i in range(n)])


def test_generate_hypotheses_empty_when_no_behavior_outcome_data():
    result = generate_hypotheses(pd.DataFrame())
    assert len(result) == 0
    assert list(result.columns) == list(Hypothesis.__annotations__.keys())


def test_generate_hypotheses_produces_valid_record():
    outcome = _outcome_rows(n=2)
    result = generate_hypotheses(outcome)
    assert len(result) == 1
    row = result.iloc[0]
    assert row.mechanism_id == "BM-001"
    assert row.sample_size == 2
    assert "Status Quo Bias" in row.hypothesis_statement


def test_hypothesis_schema_matches_required_fields():
    required = {
        "hypothesis_id", "mechanism_id", "scenario_id", "journey_stage", "population",
        "segment", "outcome_variable", "null_hypothesis", "alternative_hypothesis",
        "comparison_group", "sample_size", "discovery_dataset_reference", "status",
        "created_date", "tested_date", "validation_status",
    }
    assert required <= set(Hypothesis.__annotations__.keys())


def test_status_vocabulary_matches_spec():
    assert HYPOTHESIS_STATUSES == {
        "PROPOSED", "ELIGIBLE_FOR_TESTING", "TESTED", "SUPPORTED", "NOT_SUPPORTED",
        "INCONCLUSIVE", "HELD_OUT_PENDING", "REPLICATED", "FAILED_REPLICATION",
    }


def test_eligibility_below_threshold_stays_proposed():
    outcome = _outcome_rows(n=1)  # below minimum_sample_size and minimum_unique_applications
    result = generate_hypotheses(outcome)
    assert result.iloc[0].status == "PROPOSED"


def test_eligibility_at_threshold_becomes_eligible():
    n = max(ELIGIBILITY_CONFIG["minimum_sample_size"], ELIGIBILITY_CONFIG["minimum_unique_applications"])
    outcome = _outcome_rows(n=n)
    result = generate_hypotheses(outcome)
    assert result.iloc[0].status == "ELIGIBLE_FOR_TESTING"


def test_eligibility_config_clearly_labeled_non_scientific():
    assert "NOT SCIENTIFICALLY VALIDATED" in ELIGIBILITY_CONFIG["_label"]


def test_scenario_id_attached_when_scenario_library_provided():
    outcome = _outcome_rows(n=2)
    scenarios = pd.DataFrame([{
        "scenario_id": "SCN-001", "scenario_name": "x", "mechanism_id": "BM-001",
        "mechanism_name": "Status Quo Bias", "observable_evidence": "x", "journey_stage": "offer_accepted",
        "alternative_explanation": "x", "information_gap": "x", "outcome_association": "x",
    }])
    result = generate_hypotheses(outcome, scenario_library=scenarios)
    assert result.iloc[0].scenario_id == "SCN-001"
    assert result.iloc[0].journey_stage == "offer_accepted"


def test_scenario_id_blank_when_no_scenario_library():
    outcome = _outcome_rows(n=2)
    result = generate_hypotheses(outcome, scenario_library=None)
    assert result.iloc[0].scenario_id == ""
    assert result.iloc[0].journey_stage == "unknown"


def test_hypothesis_statement_does_not_claim_truth():
    outcome = _outcome_rows(n=2)
    result = generate_hypotheses(outcome)
    statement = result.iloc[0].hypothesis_statement.lower()
    assert "will show" in statement or "different" in statement
    assert "proven" not in statement and "is true" not in statement and "causes" not in statement


def test_multiple_mechanisms_produce_multiple_hypotheses():
    outcome = pd.concat([_outcome_rows(mech_id="BM-001", mech_name="Status Quo Bias", n=2),
                          _outcome_rows(mech_id="BM-002", mech_name="Loss Aversion", n=2)], ignore_index=True)
    result = generate_hypotheses(outcome)
    assert len(result) == 2
    assert set(result.mechanism_id) == {"BM-001", "BM-002"}


def test_created_date_populated_tested_date_and_validation_status_blank_until_tested():
    outcome = _outcome_rows(n=2)
    result = generate_hypotheses(outcome)
    row = result.iloc[0]
    assert row.created_date  # non-empty
    assert row.tested_date == ""
    assert row.validation_status == ""


def test_demo_illustration_is_clearly_labeled_and_not_a_real_record():
    demo = demo_hypothesis_illustration()
    assert "ILLUSTRATIVE" in demo["status"]
    assert demo["hypothesis_id"] == "HYP-DEMO-EXAMPLE"
