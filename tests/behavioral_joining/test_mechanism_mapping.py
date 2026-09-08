import pytest
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.behavioral_joining.mechanism_library import load_mechanism_library, MechanismLibraryResult
from src.behavioral_joining.mechanism_mapping import map_mechanism, RuleBasedMechanismMapperBackend
from src.behavioral_joining.mechanism_mapping_review import (
    initialize_mapping_review_file, approve_mapping, reject_mapping, change_mechanism,
    add_alternative_interpretation, get_approved_or_edited_mappings,
)


def test_mechanism_library_search_is_honest_about_current_state():
    """Documents whatever the real current repository state is -- passes either way,
    so this test doesn't silently break as the library goes from missing to present."""
    result = load_mechanism_library()
    assert result.status in ("LOADED", "NOT_FOUND")
    if result.status == "NOT_FOUND":
        assert result.mechanisms == []
        assert len(result.paths_checked) > 0
        assert "not found" in result.error.lower() or "no replacement" in result.error.lower()


def test_real_frozen_mechanism_library_loads_with_exactly_34_mechanisms():
    """The real behavioral_mechanisms.json (Aaryatech Behavioral Mechanism Library
    V1.0) has now been supplied. This asserts it loads correctly and contains exactly
    the frozen BM-001..BM-034 set with no duplicates -- if this ever fails, it means
    the source-of-truth file has changed or gone missing, which should be investigated
    immediately rather than silently tolerated."""
    result = load_mechanism_library()
    assert result.status == "LOADED", (
        f"Expected the real mechanism library to be loaded; got status={result.status}, "
        f"error={result.error}"
    )
    assert len(result.mechanisms) == 34
    ids = [m["Pattern_ID"] for m in result.mechanisms]
    assert len(set(ids)) == 34, "duplicate Pattern_ID values found"
    assert sorted(ids) == [f"BM-{i:03d}" for i in range(1, 35)]


def test_mechanism_library_loads_valid_fixture(tmp_path):
    """If a well-formed library file IS present, it loads correctly and completely."""
    fixture = tmp_path / "behavioral_mechanisms.json"
    fixture.write_text(
        '[{"Pattern_ID": "BM-001", "Pattern_Name": "Example Mechanism", '
        '"keywords": ["alpha", "beta"]}]'
    )
    result = load_mechanism_library(extra_paths=[fixture], only_extra_paths=True)
    assert result.status == "LOADED"
    assert len(result.mechanisms) == 1
    assert result.mechanisms[0]["Pattern_ID"] == "BM-001"


def test_mechanism_library_rejects_malformed_json(tmp_path):
    fixture = tmp_path / "behavioral_mechanisms.json"
    fixture.write_text("{not valid json")
    result = load_mechanism_library(extra_paths=[fixture], only_extra_paths=True)
    assert result.status == "NOT_FOUND"
    assert "not valid json" in result.error.lower()


def test_mechanism_library_rejects_entries_missing_required_fields(tmp_path):
    fixture = tmp_path / "behavioral_mechanisms.json"
    fixture.write_text('[{"Pattern_ID": "BM-001"}]')  # missing Pattern_Name
    result = load_mechanism_library(extra_paths=[fixture], only_extra_paths=True)
    assert result.status == "NOT_FOUND"
    assert "missing required fields" in result.error.lower()


def _fake_approved_evidence():
    return pd.DataFrame([
        {"evidence_id": "EV-1", "application_id": "APP-1", "evidence_span": "text about alpha and beta",
         "context_before": "", "context_after": "", "evidence_description": ""},
        {"evidence_id": "EV-2", "application_id": "APP-2", "evidence_span": "nothing relevant here",
         "context_before": "", "context_after": "", "evidence_description": ""},
    ])


def test_map_mechanism_returns_no_supported_mechanism_when_library_not_loaded():
    not_found = MechanismLibraryResult(status="NOT_FOUND", mechanisms=[], error="not found (test)")
    mappings = map_mechanism(_fake_approved_evidence(), not_found)
    assert len(mappings) == 2
    assert (mappings.mechanism_id == "").all()
    assert (mappings.mapping_reason.str.contains("NO SUPPORTED MECHANISM")).all()


def test_map_mechanism_proposes_only_with_sufficient_keyword_support():
    lib = MechanismLibraryResult(
        status="LOADED",
        mechanisms=[{"mechanism_id": "M01", "mechanism_name": "Example", "keywords": ["alpha", "beta"]}],
    )
    mappings = map_mechanism(_fake_approved_evidence(), lib, backend=RuleBasedMechanismMapperBackend())
    row1 = mappings[mappings.evidence_id == "EV-1"].iloc[0]
    row2 = mappings[mappings.evidence_id == "EV-2"].iloc[0]
    assert row1.mechanism_id == "M01"           # both keywords present -> proposed
    assert row2.mechanism_id == ""               # no keyword overlap -> NO SUPPORTED MECHANISM


def test_map_mechanism_never_proposes_on_single_keyword_hit():
    """Guards against naive single-keyword matching (e.g. 'salary' -> loss aversion)."""
    lib = MechanismLibraryResult(
        status="LOADED",
        mechanisms=[{"mechanism_id": "M02", "mechanism_name": "Compensation-linked", "keywords": ["salary", "raise"]}],
    )
    evidence = pd.DataFrame([{"evidence_id": "EV-3", "application_id": "APP-3",
                               "evidence_span": "candidate mentioned salary once",
                               "context_before": "", "context_after": "", "evidence_description": ""}])
    mappings = map_mechanism(evidence, lib, backend=RuleBasedMechanismMapperBackend())
    assert mappings.iloc[0].mechanism_id == ""  # only 1 of 2 keywords present -> no proposal


def test_mapping_review_workflow_preserves_original():
    candidates = pd.DataFrame([{
        "mapping_id": "MAP-1", "evidence_id": "EV-1", "application_id": "APP-1",
        "mechanism_id": "M01", "mechanism_name": "Example", "mapping_reason": "reason text",
        "evidence_support_level": "weak", "mapping_confidence": 0.35,
        "alternative_interpretation": "alt text", "review_status": "pending", "reviewer_notes": "",
    }])
    review = initialize_mapping_review_file(candidates)
    assert review.iloc[0].review_decision == "pending"
    assert review.iloc[0].original_mechanism_id == "M01"

    approved = approve_mapping(review, "MAP-1", "analyst", "confirmed")
    assert approved.iloc[0].review_decision == "approved"
    assert approved.iloc[0].original_mechanism_id == "M01"  # unchanged

    changed = change_mechanism(review, "MAP-1", "analyst", "M02", "Different Mechanism", "reconsidered")
    assert changed.iloc[0].review_decision == "edited"
    assert changed.iloc[0].edited_mechanism_id == "M02"
    assert changed.iloc[0].original_mechanism_id == "M01"  # still preserved


def test_mapping_review_supports_rejection():
    candidates = pd.DataFrame([{
        "mapping_id": "MAP-2", "evidence_id": "EV-2", "application_id": "APP-2",
        "mechanism_id": "", "mechanism_name": "", "mapping_reason": "NO SUPPORTED MECHANISM",
        "evidence_support_level": "insufficient", "mapping_confidence": 0.0,
        "alternative_interpretation": "", "review_status": "pending", "reviewer_notes": "",
    }])
    review = initialize_mapping_review_file(candidates)
    rejected = reject_mapping(review, "MAP-2", "analyst", "confirmed no mechanism applies")
    assert rejected.iloc[0].review_decision == "rejected"


def test_get_approved_or_edited_mappings_filters_correctly():
    candidates = pd.DataFrame([
        {"mapping_id": "MAP-A", "evidence_id": "EV-A", "application_id": "APP-A", "mechanism_id": "M01",
         "mechanism_name": "X", "mapping_reason": "r", "evidence_support_level": "weak",
         "mapping_confidence": 0.3, "alternative_interpretation": "", "review_status": "pending", "reviewer_notes": ""},
        {"mapping_id": "MAP-B", "evidence_id": "EV-B", "application_id": "APP-B", "mechanism_id": "",
         "mechanism_name": "", "mapping_reason": "NO SUPPORTED MECHANISM", "evidence_support_level": "insufficient",
         "mapping_confidence": 0.0, "alternative_interpretation": "", "review_status": "pending", "reviewer_notes": ""},
    ])
    review = initialize_mapping_review_file(candidates)
    review = approve_mapping(review, "MAP-A", "analyst")
    review = reject_mapping(review, "MAP-B", "analyst")
    result = get_approved_or_edited_mappings(review)
    assert list(result.mapping_id) == ["MAP-A"]
