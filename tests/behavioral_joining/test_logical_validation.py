import pytest
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.behavioral_joining.data_loader import load_dataset, RAW_DIR
from src.behavioral_joining.logical_validation import validate_logic


@pytest.fixture(scope="module")
def dataset():
    return load_dataset(RAW_DIR)


def test_logical_validation_passes(dataset):
    result = validate_logic(dataset)
    assert result.passed, result.summary()


def test_actual_start_date_null_for_non_starters(dataset):
    apps = dataset.applications
    non_starters = ["accepted_no_show", "withdrew_post_acceptance", "declined_offer"]
    bad = apps[apps.final_disposition.isin(non_starters) & apps.actual_start_date.notna()]
    assert len(bad) == 0


def test_offer_accepted_true_for_expected_dispositions(dataset):
    apps = dataset.applications
    true_required = ["joined_on_time", "joined_late", "accepted_no_show", "withdrew_post_acceptance"]
    for disp in true_required:
        bad = apps[(apps.final_disposition == disp) & (apps.offer_accepted != True)]
        assert len(bad) == 0, f"{disp} has offer_accepted != True rows"


def test_offer_accepted_false_for_declined(dataset):
    apps = dataset.applications
    bad = apps[(apps.final_disposition == "declined_offer") & (apps.offer_accepted != False)]
    assert len(bad) == 0


def test_expected_start_after_offer_response(dataset):
    apps = dataset.applications
    assert (apps.expected_start_date >= apps.offer_response_date).all()


def test_joined_late_after_expected(dataset):
    apps = dataset.applications
    jl = apps[apps.final_disposition == "joined_late"]
    assert (jl.actual_start_date > jl.expected_start_date).all()


def test_chronology_application_to_response(dataset):
    apps = dataset.applications
    ok = ((apps.application_date <= apps.interview_date) &
          (apps.interview_date <= apps.offer_date) &
          (apps.offer_date <= apps.offer_response_date))
    assert ok.all()


def test_communications_not_before_application(dataset):
    comms = dataset.communications.merge(
        dataset.applications[["application_id", "application_date"]],
        on="application_id", how="left"
    )
    assert (comms.timestamp >= comms.application_date).all()


def test_stage_events_chronologically_ordered_per_application(dataset):
    stages = dataset.stage_events.sort_values(["application_id", "stage_timestamp"])
    bad_apps = 0
    for _, sub in stages.groupby("application_id"):
        diffs = sub.stage_timestamp.diff().dropna()
        if (diffs.dt.days < 0).any():
            bad_apps += 1
    assert bad_apps == 0
