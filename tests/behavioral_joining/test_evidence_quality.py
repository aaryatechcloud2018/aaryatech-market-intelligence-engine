import pytest
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.behavioral_joining.evidence_quality import assess_evidence_quality, DUPLICATION_STATUSES


def _fake_evidence():
    return pd.DataFrame([
        {"evidence_id": "EV-1", "application_id": "APP-1", "log_id": "LOG-1",
         "evidence_span": "ok", "evidence_category": "responsiveness"},
        {"evidence_id": "EV-2", "application_id": "APP-1", "log_id": "LOG-1",
         "evidence_span": "ok", "evidence_category": "candidate_questions"},  # same log, diff category
        {"evidence_id": "EV-3", "application_id": "APP-2", "log_id": "LOG-2",
         "evidence_span": "I would like to formally withdraw from this opportunity, thank you",
         "evidence_category": "withdrawal_language"},
        {"evidence_id": "EV-4", "application_id": "APP-3", "log_id": "LOG-3",
         "evidence_span": "ok", "evidence_category": "responsiveness"},
    ] + [
        {"evidence_id": f"EV-TMPL-{i}", "application_id": f"APP-TMPL-{i}", "log_id": f"LOG-TMPL-{i}",
         "evidence_span": "Routine check-in with candidate, no concerns noted.",
         "evidence_category": "recruiter_follow_up"}
        for i in range(10)
    ])


def test_quality_file_creation_does_not_modify_original():
    ev = _fake_evidence()
    original_cols = set(ev.columns)
    quality = assess_evidence_quality(ev)
    assert set(ev.columns) == original_cols  # original untouched
    assert "evidence_span" not in quality.columns  # separate enriched file, not a copy


def test_quality_row_count_matches_evidence():
    ev = _fake_evidence()
    quality = assess_evidence_quality(ev)
    assert len(quality) == len(ev)


def test_exact_duplicate_flagging():
    ev = _fake_evidence()
    quality = assess_evidence_quality(ev)
    ok_rows = quality[quality.evidence_id.isin(["EV-1", "EV-4"])]
    assert (ok_rows.exact_text_duplicate_count >= 2).all()


def test_same_application_duplicate_flag():
    ev = _fake_evidence()
    quality = assess_evidence_quality(ev)
    row = quality[quality.evidence_id == "EV-1"].iloc[0]
    # EV-1 and EV-2 are same application, same log, same text
    assert row.same_application_duplicate == True or row.multi_category_span == True


def test_same_log_multi_category_detected():
    ev = _fake_evidence()
    quality = assess_evidence_quality(ev)
    row1 = quality[quality.evidence_id == "EV-1"].iloc[0]
    row2 = quality[quality.evidence_id == "EV-2"].iloc[0]
    assert row1.same_log_multi_category_count == 2
    assert row2.same_log_multi_category_count == 2
    assert row1.multi_category_span
    assert row2.multi_category_span


def test_high_frequency_template_detected():
    ev = _fake_evidence()
    quality = assess_evidence_quality(ev)
    tmpl_rows = quality[quality.evidence_id.str.startswith("EV-TMPL")]
    assert tmpl_rows.is_high_frequency_template.all()
    assert (tmpl_rows.duplication_status == "likely_template").all()


def test_unique_text_classified_unique():
    ev = _fake_evidence()
    quality = assess_evidence_quality(ev)
    row = quality[quality.evidence_id == "EV-3"].iloc[0]
    assert row.duplication_status == "unique"
    assert row.information_quality == "high"


def test_short_generic_text_is_low_information_quality():
    ev = _fake_evidence()
    quality = assess_evidence_quality(ev)
    row = quality[quality.evidence_id == "EV-4"].iloc[0]
    assert row.information_quality == "low"


def test_duplication_status_values_within_allowed_set():
    ev = _fake_evidence()
    quality = assess_evidence_quality(ev)
    assert set(quality.duplication_status.unique()) <= DUPLICATION_STATUSES


def test_quality_notes_populated():
    ev = _fake_evidence()
    quality = assess_evidence_quality(ev)
    assert (quality.quality_notes.str.len() > 0).all()


def test_real_evidence_candidates_quality_runs_cleanly():
    """Smoke test against the real, current evidence candidates file."""
    from src.behavioral_joining.data_loader import RAW_DIR
    processed_path = Path(__file__).resolve().parents[2] / "data" / "behavioral_joining" / "processed" / \
        "behavioral_evidence_candidates.csv"
    if not processed_path.exists():
        pytest.skip("behavioral_evidence_candidates.csv not yet generated")
    ev = pd.read_csv(processed_path)
    quality = assess_evidence_quality(ev)
    assert len(quality) == len(ev)
    assert quality.evidence_id.is_unique
