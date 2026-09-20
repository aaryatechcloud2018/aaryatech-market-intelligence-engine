import pytest
import pandas as pd
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.behavioral_joining.import_master_approved_review import (
    build_mechanism_review_from_workbook,
)
from src.behavioral_joining.mechanism_mapping import MAPPING_V2_COLUMNS

FROZEN_LIBRARY_PATH = Path(__file__).resolve().parents[2] / "data" / "behavioral_joining" / "reference" / "behavioral_mechanisms.json"


def _wb_df():
    return pd.DataFrame([
        {"evidence_id": "EV-1", "application_id": "APP-1", "proposed_behavioral_mechanism_id": "BM-001",
         "proposed_behavioral_mechanism_name": "Status Quo Bias", "behavioral_mapping_reason": "r",
         "behavioral_mapping_confidence": 0.6, "alternative_behavioral_interpretation": "",
         "behavioral_mapping_status": "HUMAN_APPROVED", "human_decision": "APPROVE"},
        {"evidence_id": "EV-2", "application_id": "APP-2", "proposed_behavioral_mechanism_id": "NO_SUPPORTED_MECHANISM",
         "proposed_behavioral_mechanism_name": "No supported mechanism", "behavioral_mapping_reason": "r2",
         "behavioral_mapping_confidence": 0.0, "alternative_behavioral_interpretation": "",
         "behavioral_mapping_status": "HUMAN_REVIEWED_NO_SUPPORTED_MECHANISM", "human_decision": "APPROVE"},
    ])


def test_import_produces_correct_schema():
    result = build_mechanism_review_from_workbook(_wb_df())
    assert list(result.columns) == MAPPING_V2_COLUMNS


def test_supported_row_gets_real_mechanism_id():
    result = build_mechanism_review_from_workbook(_wb_df())
    row = result[result.evidence_id == "EV-1"].iloc[0]
    assert row.mechanism_id == "BM-001"
    assert row.mapping_status == "PROPOSED"
    assert row.human_mapping_decision == "APPROVE"


def test_no_supported_mechanism_row_gets_empty_mechanism_id():
    result = build_mechanism_review_from_workbook(_wb_df())
    row = result[result.evidence_id == "EV-2"].iloc[0]
    assert row.mechanism_id == ""
    assert row.mapping_status == "NO_SUPPORTED_MECHANISM"
    assert row.human_mapping_decision == "APPROVE"


def test_no_supported_mechanism_excluded_from_downstream_via_existing_filter():
    from src.behavioral_joining.scenario_mapping import get_human_approved_mappings
    result = build_mechanism_review_from_workbook(_wb_df())
    eligible = get_human_approved_mappings(result)
    assert list(eligible.evidence_id) == ["EV-1"]


def test_frozen_library_hash_unchanged_after_import():
    before = hashlib.md5(FROZEN_LIBRARY_PATH.read_bytes()).hexdigest()
    build_mechanism_review_from_workbook(_wb_df())
    after = hashlib.md5(FROZEN_LIBRARY_PATH.read_bytes()).hexdigest()
    assert before == after


def test_importer_is_idempotent():
    r1 = build_mechanism_review_from_workbook(_wb_df())
    r2 = build_mechanism_review_from_workbook(_wb_df())
    pd.testing.assert_frame_equal(r1, r2)
