import pytest
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.behavioral_joining.hypothesis_engine import (
    generate_hypotheses, demo_hypothesis_illustration, Hypothesis,
)


def test_generate_hypotheses_returns_empty_when_no_approved_mappings():
    result = generate_hypotheses(pd.DataFrame(), pd.DataFrame())
    assert len(result) == 0
    assert list(result.columns) == list(Hypothesis.__annotations__.keys())


def test_generate_hypotheses_returns_empty_when_mappings_have_no_mechanism_id():
    approved_mappings = pd.DataFrame([{
        "mapping_id": "MAP-1", "evidence_id": "EV-1", "application_id": "APP-1",
        "original_mechanism_id": "", "original_mechanism_name": "", "review_decision": "approved",
        "edited_mechanism_id": "", "edited_mechanism_name": "",
    }])
    result = generate_hypotheses(pd.DataFrame(), approved_mappings)
    assert len(result) == 0


def test_generate_hypotheses_produces_valid_records_from_real_approved_mappings():
    approved_mappings = pd.DataFrame([
        {"mapping_id": "MAP-1", "evidence_id": "EV-1", "application_id": "APP-1",
         "original_mechanism_id": "M01", "original_mechanism_name": "Example Mechanism",
         "review_decision": "approved", "edited_mechanism_id": "", "edited_mechanism_name": ""},
        {"mapping_id": "MAP-2", "evidence_id": "EV-2", "application_id": "APP-2",
         "original_mechanism_id": "M01", "original_mechanism_name": "Example Mechanism",
         "review_decision": "edited", "edited_mechanism_id": "M01", "edited_mechanism_name": "Example Mechanism"},
    ])
    result = generate_hypotheses(pd.DataFrame(), approved_mappings)
    assert len(result) == 1
    row = result.iloc[0]
    assert row.mechanism_id == "M01"
    assert row.supporting_evidence_count == 2
    assert "Example Mechanism" in row.hypothesis_statement
    assert row.status in ("draft", "ready_for_testing")


def test_hypothesis_statement_does_not_claim_truth():
    approved_mappings = pd.DataFrame([{
        "mapping_id": "MAP-1", "evidence_id": "EV-1", "application_id": "APP-1",
        "original_mechanism_id": "M01", "original_mechanism_name": "Example Mechanism",
        "review_decision": "approved", "edited_mechanism_id": "", "edited_mechanism_name": "",
    }])
    result = generate_hypotheses(pd.DataFrame(), approved_mappings)
    statement = result.iloc[0].hypothesis_statement.lower()
    assert "will show" in statement or "different" in statement
    assert "proven" not in statement and "is true" not in statement and "causes" not in statement


def test_demo_illustration_is_clearly_labeled_and_not_a_real_record():
    demo = demo_hypothesis_illustration()
    assert "ILLUSTRATIVE" in demo["status"]
    assert demo["hypothesis_id"] == "HYP-DEMO-EXAMPLE"
