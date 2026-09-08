import pytest
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.behavioral_joining.build_journey_master import build_master
from src.behavioral_joining.data_loader import RAW_DIR, FORBIDDEN_FILE


@pytest.fixture(scope="module")
def master():
    return build_master(RAW_DIR)


def test_master_row_count_matches_applications(master):
    apps = pd.read_csv(RAW_DIR / "01_candidate_applications.csv")
    assert len(master) == len(apps)


def test_master_application_id_unique(master):
    assert master.application_id.is_unique


def test_master_no_duplicate_columns(master):
    assert master.columns.is_unique


def test_master_no_communication_text_flattened(master):
    # communication_log content (free text, log_id) must never be merged into the
    # journey master -- timing/sequence evidence must stay in its own table.
    assert "text" not in master.columns
    assert "log_id" not in master.columns
    assert "source_type" not in master.columns


def test_master_no_stage_event_fields_flattened(master):
    assert "stage_name" not in master.columns
    assert "event_id" not in master.columns


def test_master_no_forbidden_behavioral_columns(master):
    forbidden_terms = ["risk_score", "probability", "prediction", "mechanism",
                        "behavioral_", "bias_", "psych"]
    leaked = [c for c in master.columns if any(t in c.lower() for t in forbidden_terms)]
    assert leaked == [], f"Forbidden columns present: {leaked}"


def test_master_contains_required_derived_variables(master):
    required = [
        "days_application_to_interview", "days_interview_to_offer", "days_offer_to_response",
        "days_acceptance_to_expected_start", "days_expected_to_actual_start",
        "pay_change_absolute", "pay_change_percentage",
        "total_stage_events", "total_communications",
    ]
    for col in required:
        assert col in master.columns, f"missing derived variable: {col}"


def test_ground_truth_file_never_referenced_in_source():
    """Static safeguard: no source file should ACTUALLY LOAD 08_scenario_ground_truth.csv.
    data_loader.py mentions it only to explicitly forbid/guard against it, and
    generate_validation_report.py mentions it only in a human-readable confirmation
    string -- neither constitutes loading the file, so both are legitimate."""
    src_dir = Path(__file__).resolve().parents[2] / "src" / "behavioral_joining"
    load_patterns = ["read_csv", "load_table(", "pd.read_csv"]
    offenders = []
    for py_file in src_dir.glob("*.py"):
        content = py_file.read_text()
        if FORBIDDEN_FILE in content:
            # flag only if the forbidden filename appears on the same line as an
            # actual load call (i.e. someone tried to read it), not just a string mention
            for line in content.splitlines():
                if FORBIDDEN_FILE in line and any(p in line for p in load_patterns):
                    offenders.append((py_file.name, line.strip()))
    assert offenders == [], f"Lines that would actually load the forbidden file: {offenders}"


def test_research_split_stratification_roughly_preserved(master):
    # Sanity check only -- confirms the split proportions carried over into the
    # master table (they are copied verbatim from applications, not recomputed).
    counts = master.research_split.value_counts(normalize=True)
    assert abs(counts.get("discovery", 0) - 0.60) < 0.02
    assert abs(counts.get("hypothesis_generation", 0) - 0.20) < 0.02
    assert abs(counts.get("held_out_test", 0) - 0.20) < 0.02
