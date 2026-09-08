import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.behavioral_joining.discovery_context import build_discovery_working_set
from src.behavioral_joining.data_loader import RAW_DIR
from src.behavioral_joining.objective_signals import compute_objective_signals


@pytest.fixture(scope="module")
def signals():
    ctx = build_discovery_working_set(RAW_DIR)
    return compute_objective_signals(ctx)


def test_signals_produced_for_all_discovery_applications(signals):
    ctx = build_discovery_working_set(RAW_DIR)
    assert len(signals) == ctx.n_discovery_applications


def test_no_forbidden_columns(signals):
    forbidden = ["risk", "probability", "predict", "score", "likelihood"]
    for col in signals.columns:
        for bad in forbidden:
            assert bad not in col.lower(), f"forbidden term '{bad}' found in column '{col}'"


def test_counts_are_non_negative(signals):
    count_cols = ["number_of_candidate_messages", "number_of_recruiter_messages",
                  "total_communications", "candidate_question_message_count",
                  "unanswered_candidate_message_count", "total_stage_events"]
    for col in count_cols:
        assert (signals[col] >= 0).all()
