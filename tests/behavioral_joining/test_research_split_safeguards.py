import pytest
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.behavioral_joining.discovery_context import (
    build_discovery_working_set, assert_outcome_blind, OUTCOME_COLUMNS,
)
from src.behavioral_joining.data_loader import RAW_DIR, FORBIDDEN_FILE, load_table
from src.behavioral_joining.statistical_engine import (
    run_held_out_validation, HeldOutTestNotAuthorizedError,
)


@pytest.fixture(scope="module")
def ctx():
    return build_discovery_working_set(RAW_DIR)


def test_discovery_only_applications(ctx):
    """Only research_split == 'discovery' rows may appear in the working set."""
    assert ctx.n_discovery_applications > 0
    assert ctx.n_discovery_applications < ctx.n_total_applications


def test_discovery_communications_scoped_to_discovery_applications(ctx):
    discovery_ids = set(pd.read_csv(RAW_DIR / "01_candidate_applications.csv")
                         .query("research_split == 'discovery'").application_id)
    assert set(ctx.communications.application_id.unique()) <= discovery_ids


def test_discovery_stage_events_scoped_to_discovery_applications(ctx):
    discovery_ids = set(pd.read_csv(RAW_DIR / "01_candidate_applications.csv")
                         .query("research_split == 'discovery'").application_id)
    assert set(ctx.stage_events.application_id.unique()) <= discovery_ids


def test_outcome_columns_stripped_from_discovery_applications(ctx):
    for col in OUTCOME_COLUMNS:
        assert col not in ctx.applications.columns


def test_assert_outcome_blind_raises_on_violation():
    bad_df = pd.DataFrame({"application_id": ["APP-1"], "final_disposition": ["joined_on_time"]})
    with pytest.raises(ValueError):
        assert_outcome_blind(bad_df)


def test_assert_outcome_blind_passes_on_clean_df():
    clean_df = pd.DataFrame({"application_id": ["APP-1"], "job_family": ["IT/Technology"]})
    assert_outcome_blind(clean_df) is None  # does not raise


def test_held_out_test_rows_not_in_discovery_context(ctx):
    held_out_ids = set(pd.read_csv(RAW_DIR / "01_candidate_applications.csv")
                        .query("research_split == 'held_out_test'").application_id)
    used_ids = set(ctx.applications.application_id) | set(ctx.communications.application_id) | \
        set(ctx.stage_events.application_id)
    assert used_ids.isdisjoint(held_out_ids)


def test_hypothesis_generation_split_not_in_discovery_context(ctx):
    """Discovery evidence extraction must use ONLY the discovery split, not
    hypothesis_generation either -- that split is reserved for the next stage."""
    hyp_gen_ids = set(pd.read_csv(RAW_DIR / "01_candidate_applications.csv")
                       .query("research_split == 'hypothesis_generation'").application_id)
    used_ids = set(ctx.applications.application_id)
    assert used_ids.isdisjoint(hyp_gen_ids)


def test_ground_truth_file_absent_from_raw_dir():
    assert not (RAW_DIR / FORBIDDEN_FILE).exists()


def test_ground_truth_file_not_loadable_by_name():
    with pytest.raises(PermissionError):
        load_table("08_scenario_ground_truth.csv")


def test_held_out_validation_blocked_by_default():
    with pytest.raises(HeldOutTestNotAuthorizedError):
        run_held_out_validation()


def test_held_out_validation_blocked_even_with_partial_authorization():
    with pytest.raises(HeldOutTestNotAuthorizedError):
        run_held_out_validation(authorized=True)  # no token supplied
    with pytest.raises(HeldOutTestNotAuthorizedError):
        run_held_out_validation(authorization_token="something")  # not authorized=True


def test_held_out_validation_still_not_implemented_even_when_authorized():
    """Full authorization gets past the guard but the analysis itself is not yet
    implemented -- this is intentional; it must not silently succeed."""
    with pytest.raises(NotImplementedError):
        run_held_out_validation(authorized=True, authorization_token="demo-token-not-a-real-approval")
