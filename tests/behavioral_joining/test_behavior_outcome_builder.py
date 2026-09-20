import pytest
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.behavioral_joining.behavior_outcome_builder import (
    build_behavior_outcome_dataset, assert_no_held_out_leakage, HeldOutLeakageError, OUTCOME_COLUMNS,
)


def _bridge():
    return pd.DataFrame([
        {"application_id": "APP-1", "mechanism_id": "BM-002", "mechanism_name": "Loss Aversion"},
        {"application_id": "APP-2", "mechanism_id": "BM-001", "mechanism_name": "Status Quo Bias"},
        {"application_id": "APP-3", "mechanism_id": "BM-001", "mechanism_name": "Status Quo Bias"},
    ])


def _apps():
    return pd.DataFrame([
        {"application_id": "APP-1", "research_split": "discovery", "final_disposition": "withdrew_post_acceptance",
         "job_family": "IT/Technology", "client_account_id": "CLI-001", "recruiter_id": "REC-001"},
        {"application_id": "APP-2", "research_split": "hypothesis_generation", "final_disposition": "joined_on_time",
         "job_family": "Healthcare", "client_account_id": "CLI-002", "recruiter_id": "REC-002"},
        {"application_id": "APP-3", "research_split": "held_out_test", "final_disposition": "joined_on_time",
         "job_family": "Healthcare", "client_account_id": "CLI-002", "recruiter_id": "REC-002"},
    ])


def test_empty_bridge_produces_empty_dataset():
    result = build_behavior_outcome_dataset(pd.DataFrame(columns=["application_id", "mechanism_id", "mechanism_name"]), _apps())
    assert len(result) == 0
    assert list(result.columns) == OUTCOME_COLUMNS


def test_held_out_application_excluded_from_output():
    result = build_behavior_outcome_dataset(_bridge(), _apps())
    assert "APP-3" not in set(result.application_id)
    assert (result.research_split == "held_out_test").sum() == 0


def test_discovery_and_hypothesis_generation_included():
    result = build_behavior_outcome_dataset(_bridge(), _apps())
    assert set(result.application_id) == {"APP-1", "APP-2"}
    assert set(result.research_split) == {"discovery", "hypothesis_generation"}


def test_assert_no_held_out_leakage_raises_on_violation():
    bad = pd.DataFrame([{"application_id": "X", "mechanism_id": "BM-001", "research_split": "held_out_test"}])
    with pytest.raises(HeldOutLeakageError):
        assert_no_held_out_leakage(bad)


def test_assert_no_held_out_leakage_passes_on_clean_data():
    clean = pd.DataFrame([{"application_id": "X", "mechanism_id": "BM-001", "research_split": "discovery"}])
    assert_no_held_out_leakage(clean) is None


def test_assert_no_held_out_leakage_raises_if_split_column_missing():
    no_split = pd.DataFrame([{"application_id": "X", "mechanism_id": "BM-001"}])
    with pytest.raises(HeldOutLeakageError):
        assert_no_held_out_leakage(no_split)


def test_build_function_always_calls_safeguard_even_on_empty_input():
    import inspect
    from src.behavioral_joining import behavior_outcome_builder
    source = inspect.getsource(behavior_outcome_builder.build_behavior_outcome_dataset)
    assert source.count("assert_no_held_out_leakage(") >= 2


def test_no_statistical_testing_performed_in_this_module():
    import inspect
    from src.behavioral_joining import behavior_outcome_builder
    source = inspect.getsource(behavior_outcome_builder)
    assert "scipy" not in source
    assert "chi_square_test" not in source
    assert "fishers_exact_test" not in source


def test_output_schema_matches_required_columns():
    result = build_behavior_outcome_dataset(_bridge(), _apps())
    assert list(result.columns) == OUTCOME_COLUMNS
