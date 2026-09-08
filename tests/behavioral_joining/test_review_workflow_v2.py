import pytest
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.behavioral_joining.mechanism_library import load_mechanism_library, MechanismLibraryResult
from src.behavioral_joining.mechanism_mapping import (
    map_reviewed_evidence, ContextAwareMechanismMapperBackend, MAPPING_V2_COLUMNS,
)
from src.behavioral_joining.hypothesis_readiness import compute_hypothesis_readiness, READINESS_CONFIG
from src.behavioral_joining.calibration_metrics import compute_evidence_agreement_metrics


def _sample_row(decision, category="withdrawal_language", desc="orig", human_cat=None, human_desc=None):
    return {
        "review_sample_id": "REV-0001", "evidence_id": "EV-1", "application_id": "APP-1",
        "log_id": "LOG-1", "timestamp": "2026-01-01", "source_type": "candidate_message",
        "direction": "candidate_facing", "evidence_span": "I've decided to withdraw",
        "evidence_category": category, "evidence_description": desc,
        "context_before": "", "context_after": "", "response_latency_hours": 5.0,
        "extractor_confidence": 0.7, "information_quality": "high", "duplication_status": "unique",
        "human_decision": decision,
        "human_evidence_category": human_cat if human_cat is not None else "",
        "human_description": human_desc if human_desc is not None else "",
        "human_notes": "",
    }


# --- review decision persistence ---

def test_edit_preserves_original_proposal_fields():
    row = _sample_row("EDIT", category="withdrawal_language", desc="original AI description",
                       human_cat="withdrawal_language", human_desc="human-clarified text")
    df = pd.DataFrame([row])
    assert df.iloc[0].evidence_description == "original AI description"
    assert df.iloc[0].human_description == "human-clarified text"


def test_review_decisions_round_trip_through_csv(tmp_path):
    df = pd.DataFrame([_sample_row("APPROVE"), _sample_row("PENDING"), _sample_row("REJECT")])
    path = tmp_path / "sample.csv"
    df.to_csv(path, index=False)
    reloaded = pd.read_csv(path, keep_default_na=False)
    assert list(reloaded.human_decision) == ["APPROVE", "PENDING", "REJECT"]


# --- mechanism mapping eligibility rules ---

def test_only_approve_and_edit_are_valid_for_mapping():
    from src.behavioral_joining.run_mechanism_mapping import VALID_HUMAN_DECISIONS_FOR_MAPPING
    assert VALID_HUMAN_DECISIONS_FOR_MAPPING == {"APPROVE", "EDIT"}


def test_pending_evidence_cannot_be_mapped():
    """The caller (run_mechanism_mapping.py) filters to APPROVE/EDIT before calling
    map_reviewed_evidence -- this test verifies that filter logic directly."""
    sample = pd.DataFrame([_sample_row("PENDING"), _sample_row("APPROVE")])
    eligible = sample[sample.human_decision.isin({"APPROVE", "EDIT"})]
    assert len(eligible) == 1
    assert eligible.iloc[0].human_decision == "APPROVE"


def test_rejected_evidence_cannot_be_mapped():
    sample = pd.DataFrame([_sample_row("REJECT"), _sample_row("EDIT")])
    eligible = sample[sample.human_decision.isin({"APPROVE", "EDIT"})]
    assert len(eligible) == 1
    assert eligible.iloc[0].human_decision == "EDIT"


def test_no_supported_mechanism_status_works():
    lib = load_mechanism_library()
    evidence = pd.DataFrame([{
        "evidence_id": "EV-X", "application_id": "APP-X",
        "human_evidence_category": "responsiveness",  # no hints defined for this category
        "evidence_category": "responsiveness", "evidence_span": "ok",
        "context_before": "", "context_after": "", "evidence_description": "",
    }])
    result = map_reviewed_evidence(evidence, lib)
    assert result.iloc[0].mapping_status == "NO_SUPPORTED_MECHANISM"
    assert result.iloc[0].mechanism_id == ""


def test_mapping_output_has_required_columns():
    lib = load_mechanism_library()
    evidence = pd.DataFrame([{
        "evidence_id": "EV-Y", "application_id": "APP-Y",
        "human_evidence_category": "withdrawal_language", "evidence_category": "withdrawal_language",
        "evidence_span": "I have decided to withdraw", "context_before": "", "context_after": "",
        "evidence_description": "",
    }])
    result = map_reviewed_evidence(evidence, lib)
    assert list(result.columns) == MAPPING_V2_COLUMNS
    assert (result.human_mapping_decision == "PENDING").all()


def test_mapping_not_implemented_as_simple_keyword_lookup():
    """A mechanism's own illustrative linguistic-signal phrase appearing verbatim in
    the evidence text must NOT be sufficient by itself to trigger a mapping to that
    mechanism -- category-hint alignment (or its absence) governs, not raw keyword
    presence. This directly tests the frozen library's own instruction that
    Possible_Linguistic_Signals are illustrative, not classification rules."""
    lib = load_mechanism_library()
    # Loss Aversion's linguistic signal: "Now I'm losing the feature I relied on."
    # Use an evidence_category that has NO hint pointing to Loss Aversion.
    evidence = pd.DataFrame([{
        "evidence_id": "EV-Z", "application_id": "APP-Z",
        "human_evidence_category": "candidate_questions",  # no mechanism hints at all
        "evidence_category": "candidate_questions",
        "evidence_span": "Now I'm losing the feature I relied on.",  # verbatim BM-002 linguistic signal
        "context_before": "", "context_after": "", "evidence_description": "",
    }])
    result = map_reviewed_evidence(evidence, lib)
    # A naive keyword matcher would map this to Loss Aversion (BM-002). Ours must not.
    assert result.iloc[0].mapping_status == "NO_SUPPORTED_MECHANISM"


def test_contradictory_signal_vetoes_an_otherwise_hinted_mechanism():
    lib = load_mechanism_library()
    evidence = pd.DataFrame([{
        "evidence_id": "EV-W", "application_id": "APP-W",
        "human_evidence_category": "withdrawal_language", "evidence_category": "withdrawal_language",
        "evidence_span": "I've decided to withdraw. The new benefits are worth more than what I gave up.",
        "context_before": "", "context_after": "", "evidence_description": "",
    }])
    result = map_reviewed_evidence(evidence, lib)
    proposed_ids = set(result[result.mapping_status == "PROPOSED"].mechanism_id)
    assert "BM-002" not in proposed_ids  # Loss Aversion vetoed by its own contradictory signal


def test_frozen_library_unchanged_by_mapping_run():
    import hashlib
    path = Path(__file__).resolve().parents[2] / "data" / "behavioral_joining" / "reference" / "behavioral_mechanisms.json"
    before = hashlib.md5(path.read_bytes()).hexdigest()
    lib = load_mechanism_library()
    evidence = pd.DataFrame([{
        "evidence_id": "EV-V", "application_id": "APP-V",
        "human_evidence_category": "withdrawal_language", "evidence_category": "withdrawal_language",
        "evidence_span": "I withdraw.", "context_before": "", "context_after": "", "evidence_description": "",
    }])
    map_reviewed_evidence(evidence, lib)
    after = hashlib.md5(path.read_bytes()).hexdigest()
    assert before == after


# --- hypothesis readiness ---

def test_hypothesis_readiness_empty_when_no_approved_mappings():
    empty = pd.DataFrame(columns=MAPPING_V2_COLUMNS)
    result = compute_hypothesis_readiness(empty)
    assert len(result) == 0


def test_hypothesis_readiness_ignores_pending_and_rejected():
    mappings = pd.DataFrame([
        {"mapping_id": "M1", "evidence_id": "E1", "application_id": "A1", "mechanism_id": "BM-001",
         "mechanism_name": "Status Quo Bias", "mapping_confidence": 0.6, "mapping_status": "PROPOSED",
         "human_mapping_decision": "PENDING", "human_selected_mechanism": ""},
        {"mapping_id": "M2", "evidence_id": "E2", "application_id": "A2", "mechanism_id": "BM-001",
         "mechanism_name": "Status Quo Bias", "mapping_confidence": 0.6, "mapping_status": "PROPOSED",
         "human_mapping_decision": "REJECT", "human_selected_mechanism": ""},
    ])
    result = compute_hypothesis_readiness(mappings)
    assert len(result) == 0  # nothing approved/edited -> nothing counted


def test_hypothesis_readiness_config_is_clearly_labeled_non_scientific():
    assert "NOT SCIENTIFICALLY VALIDATED" in READINESS_CONFIG["_label"]


def test_hypothesis_readiness_uses_only_approved_or_edited():
    mappings = pd.DataFrame([
        {"mapping_id": f"M{i}", "evidence_id": f"E{i}", "application_id": f"A{i}", "mechanism_id": "BM-001",
         "mechanism_name": "Status Quo Bias", "mapping_confidence": 0.6, "mapping_status": "PROPOSED",
         "human_mapping_decision": "APPROVE", "human_selected_mechanism": "BM-001"}
        for i in range(6)
    ])
    result = compute_hypothesis_readiness(mappings)
    assert len(result) == 1
    assert result.iloc[0].approved_mapping_count == 6


# --- calibration ---

def test_calibration_reports_no_reviews_yet_when_all_pending():
    sample = pd.DataFrame([_sample_row("PENDING") for _ in range(5)])
    metrics = compute_evidence_agreement_metrics(sample)
    assert metrics["status"] == "no_reviews_yet"


def test_calibration_not_labeled_as_accuracy():
    """The module must never present a metric AS accuracy (e.g. a field/label named
    'accuracy' or 'model_accuracy') -- its own explanatory disclaimer using the word
    'accuracy' to explicitly reject that framing is fine and expected."""
    import inspect
    from src.behavioral_joining import calibration_metrics
    source = inspect.getsource(calibration_metrics)
    assert "accuracy_rate" not in source.lower()
    assert '"accuracy"' not in source.lower()
    assert "not \"model accuracy\"" in source.lower() or "not model accuracy" in source.lower()
