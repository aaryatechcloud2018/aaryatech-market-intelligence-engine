import pytest
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.behavioral_joining.data_loader import RAW_DIR
from src.behavioral_joining.evidence_quality import assess_evidence_quality
from src.behavioral_joining.review_sampling import build_review_sample, TARGET_SAMPLE_SIZE

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "behavioral_joining" / "processed"


@pytest.fixture(scope="module")
def evidence_and_quality():
    path = PROCESSED_DIR / "behavioral_evidence_candidates.csv"
    if not path.exists():
        pytest.skip("behavioral_evidence_candidates.csv not yet generated")
    ev = pd.read_csv(path)
    quality = assess_evidence_quality(ev)
    return ev, quality


@pytest.fixture(scope="module")
def sample(evidence_and_quality):
    ev, quality = evidence_and_quality
    return build_review_sample(ev, quality)


def test_sample_size_approximately_250(sample):
    assert 200 <= len(sample) <= 320


def test_sample_review_ids_unique(sample):
    assert sample.review_sample_id.is_unique


def test_sample_evidence_ids_unique(sample):
    assert sample.evidence_id.is_unique


def test_all_categories_represented_where_possible(sample, evidence_and_quality):
    ev, _ = evidence_and_quality
    all_categories = set(ev.evidence_category.unique())
    sample_categories = set(sample.evidence_category.unique())
    # allow small shortfall only if a category is extremely rare in the source data
    missing = all_categories - sample_categories
    for cat in missing:
        assert (ev.evidence_category == cat).sum() < 5, f"category '{cat}' missing from sample despite having enough source rows"


def test_sample_excludes_held_out(sample):
    apps = pd.read_csv(RAW_DIR / "01_candidate_applications.csv")
    held_out_ids = set(apps[apps.research_split == "held_out_test"].application_id)
    assert set(sample.application_id).isdisjoint(held_out_ids)


def test_sample_excludes_hypothesis_generation(sample):
    apps = pd.read_csv(RAW_DIR / "01_candidate_applications.csv")
    hyp_gen_ids = set(apps[apps.research_split == "hypothesis_generation"].application_id)
    assert set(sample.application_id).isdisjoint(hyp_gen_ids)


def test_sample_only_discovery_split(sample):
    apps = pd.read_csv(RAW_DIR / "01_candidate_applications.csv")
    discovery_ids = set(apps[apps.research_split == "discovery"].application_id)
    assert set(sample.application_id) <= discovery_ids


def test_sample_does_not_expose_final_disposition(sample):
    forbidden = {"final_disposition", "disposition_date", "actual_start_date"}
    assert forbidden.isdisjoint(set(sample.columns))


def test_no_single_application_dominates_sample(sample):
    max_share = sample.application_id.value_counts().iloc[0] / len(sample)
    assert max_share < 0.1  # no single application is more than 10% of the sample


def test_no_single_phrase_dominates_sample(sample):
    max_share = sample.evidence_span.value_counts().iloc[0] / len(sample)
    assert max_share < 0.1  # no single duplicated phrase is more than 10% of the sample


def test_sample_includes_low_and_high_confidence(sample):
    bands = sample.extractor_confidence.apply(lambda c: "high" if c >= 0.65 else ("medium" if c >= 0.5 else "low"))
    assert bands.nunique() >= 2  # calibration sample must include a spread, not just easy cases


def test_sample_includes_repeated_and_unique_text(sample):
    statuses = set(sample.duplication_status.unique())
    assert "unique" in statuses
    assert len(statuses) >= 2  # must include some non-unique cases too (difficult examples)


def test_sample_includes_both_candidate_and_recruiter_sources(sample):
    assert "candidate_message" in set(sample.source_type.unique())
    assert set(sample.source_type.unique()) - {"candidate_message"}  # at least one other source type


def test_all_rows_start_pending(sample):
    assert (sample.human_decision == "PENDING").all()
    assert (sample.human_evidence_category == "").all()
    assert (sample.human_description == "").all()
    assert (sample.human_notes == "").all()
