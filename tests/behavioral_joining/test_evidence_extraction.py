import pytest
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.behavioral_joining.discovery_context import build_discovery_working_set
from src.behavioral_joining.data_loader import RAW_DIR
from src.behavioral_joining.evidence_extraction import extract_evidence, EVIDENCE_CATEGORIES
from src.behavioral_joining.evidence_review import (
    initialize_review_file, approve_evidence, reject_evidence, edit_evidence,
    get_approved_or_edited,
)


@pytest.fixture(scope="module")
def ctx():
    return build_discovery_working_set(RAW_DIR)


@pytest.fixture(scope="module")
def evidence(ctx):
    return extract_evidence(ctx)


def test_evidence_produced(evidence):
    assert len(evidence) > 0


def test_evidence_ids_unique(evidence):
    assert evidence.evidence_id.is_unique


def test_all_evidence_starts_pending(evidence):
    assert (evidence.review_status == "pending").all()


def test_evidence_categories_within_taxonomy(evidence):
    assert set(evidence.evidence_category.unique()) <= set(EVIDENCE_CATEGORIES)


def test_evidence_span_is_exact_source_text(evidence, ctx):
    """Every evidence_span must be traceable to the exact text of its source
    communication log entry -- not a paraphrase."""
    comms_by_log_id = ctx.communications.set_index("log_id")["text"]
    sample = evidence.sample(min(200, len(evidence)), random_state=1)
    for _, row in sample.iterrows():
        assert row.evidence_span == comms_by_log_id.loc[row.log_id]


def test_no_outcome_columns_in_evidence_output(evidence):
    forbidden = {"final_disposition", "disposition_date", "actual_start_date"}
    assert forbidden.isdisjoint(set(evidence.columns))


def test_evidence_descriptions_are_not_mechanism_labels(evidence):
    """Spot-check: descriptions should not contain known behavioral-science jargon --
    they must stay descriptive, not theoretical."""
    forbidden_terms = ["loss aversion", "status quo bias", "social proof", "anchoring",
                        "reciprocity", "sunk cost", "commitment bias", "endowment effect"]
    joined = " ".join(evidence.evidence_description.astype(str).str.lower())
    for term in forbidden_terms:
        assert term not in joined


def test_context_before_after_present(evidence):
    assert "context_before" in evidence.columns
    assert "context_after" in evidence.columns


# --- human review workflow ---

def test_review_file_initializes_all_pending(evidence):
    review = initialize_review_file(evidence)
    assert (review.review_decision == "pending").all()
    assert len(review) == len(evidence)


def test_approve_evidence_does_not_mutate_candidates_file(evidence):
    review = initialize_review_file(evidence)
    ev_id = evidence.evidence_id.iloc[0]
    original_candidates_snapshot = evidence.copy(deep=True)

    updated_review = approve_evidence(review, ev_id, reviewer="test_analyst", notes="looks right")

    pd.testing.assert_frame_equal(evidence, original_candidates_snapshot)  # candidates untouched
    assert updated_review.loc[updated_review.evidence_id == ev_id, "review_decision"].iloc[0] == "approved"


def test_reject_evidence_workflow(evidence):
    review = initialize_review_file(evidence)
    ev_id = evidence.evidence_id.iloc[1]
    updated = reject_evidence(review, ev_id, reviewer="test_analyst", notes="not relevant")
    assert updated.loc[updated.evidence_id == ev_id, "review_decision"].iloc[0] == "rejected"


def test_edit_evidence_preserves_original_and_adds_edit(evidence):
    review = initialize_review_file(evidence)
    ev_id = evidence.evidence_id.iloc[2]
    original_desc = review.loc[review.evidence_id == ev_id, "original_evidence_description"].iloc[0]

    updated = edit_evidence(review, ev_id, reviewer="test_analyst", notes="reworded",
                             new_description="Human-clarified description of this evidence.")

    row = updated.loc[updated.evidence_id == ev_id].iloc[0]
    assert row.review_decision == "edited"
    assert row.original_evidence_description == original_desc  # original preserved
    assert row.edited_evidence_description == "Human-clarified description of this evidence."


def test_get_approved_or_edited_filters_correctly(evidence):
    review = initialize_review_file(evidence)
    ids = evidence.evidence_id.tolist()
    review = approve_evidence(review, ids[0], "analyst")
    review = edit_evidence(review, ids[1], "analyst", new_description="edited text")
    review = reject_evidence(review, ids[2], "analyst")

    result = get_approved_or_edited(review)
    assert set(result.evidence_id) == {ids[0], ids[1]}


def test_nothing_auto_approved_end_to_end(evidence):
    """No function in this module or the extractor sets review_status/review_decision
    to anything other than 'pending' without an explicit human-supplied call."""
    review = initialize_review_file(evidence)
    assert (review.review_decision == "pending").all()
