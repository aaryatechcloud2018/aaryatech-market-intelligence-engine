import pytest
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.behavioral_joining.data_loader import (
    load_dataset, load_table, RAW_DIR, FORBIDDEN_FILE, APPROVED_FILES,
)
from src.behavioral_joining.schema_validation import validate_files_exist, validate_schema


@pytest.fixture(scope="module")
def dataset():
    return load_dataset(RAW_DIR)


def test_raw_dir_exists():
    assert RAW_DIR.exists()


def test_forbidden_file_not_in_raw_dir():
    """08_scenario_ground_truth.csv must never live inside the analytical raw/ directory."""
    assert not (RAW_DIR / FORBIDDEN_FILE).exists()


def test_forbidden_file_not_loadable():
    with pytest.raises(PermissionError):
        load_table("ground_truth")
    with pytest.raises(PermissionError):
        load_table("08_scenario_ground_truth.csv")


def test_all_approved_files_exist():
    result = validate_files_exist(RAW_DIR)
    assert result.passed, result.summary()


def test_schema_validation_passes(dataset):
    result = validate_schema(dataset)
    assert result.passed, result.summary()


def test_applications_primary_key_unique(dataset):
    assert dataset.applications.application_id.is_unique
    assert dataset.applications.application_id.notna().all()


def test_communications_primary_key_unique(dataset):
    assert dataset.communications.log_id.is_unique


def test_stage_events_primary_key_unique(dataset):
    assert dataset.stage_events.event_id.is_unique


def test_foreign_keys_resolve(dataset):
    apps = dataset.applications
    assert apps.requisition_id.isin(dataset.requisitions.requisition_id).all()
    assert apps.client_account_id.isin(dataset.clients.client_account_id).all()
    assert apps.recruiter_id.isin(dataset.recruiters.recruiter_id).all()
    assert dataset.communications.application_id.isin(apps.application_id).all()
    assert dataset.stage_events.application_id.isin(apps.application_id).all()


def test_dates_parsed(dataset):
    date_cols = ["application_date", "interview_date", "offer_date", "offer_response_date",
                 "expected_start_date", "disposition_date"]
    for col in date_cols:
        assert pd.api.types.is_datetime64_any_dtype(dataset.applications[col])
        assert dataset.applications[col].notna().all()


def test_booleans_valid(dataset):
    assert dataset.applications.offer_extended.isin([True, False]).all()
    assert dataset.applications.offer_accepted.isin([True, False]).all()


def test_research_split_values_valid(dataset):
    valid = {"discovery", "hypothesis_generation", "held_out_test"}
    assert set(dataset.applications.research_split.unique()) <= valid


def test_final_disposition_values_valid(dataset):
    valid = {"joined_on_time", "joined_late", "accepted_no_show",
             "withdrew_post_acceptance", "declined_offer", "rejected_by_client"}
    assert set(dataset.applications.final_disposition.unique()) <= valid
