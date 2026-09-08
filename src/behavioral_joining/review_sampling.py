"""
review_sampling.py

Builds a STRATIFIED human review sample of roughly 250 evidence proposals from the
discovery split. This is a calibration sample, not a "best of" showcase -- it must
deliberately include difficult/ambiguous/templated cases, not just clean examples.
"""
import numpy as np
import pandas as pd

TARGET_SAMPLE_SIZE = 250
RANDOM_SEED = 42

REVIEW_SAMPLE_COLUMNS = [
    "review_sample_id", "evidence_id", "application_id", "log_id", "timestamp",
    "source_type", "direction", "evidence_span", "evidence_category", "evidence_description",
    "context_before", "context_after", "response_latency_hours", "extractor_confidence",
    "information_quality", "duplication_status",
    "human_decision", "human_evidence_category", "human_description", "human_notes",
]


def _confidence_band(c: float) -> str:
    if c >= 0.65:
        return "high"
    if c >= 0.5:
        return "medium"
    return "low"


def build_review_sample(evidence_candidates: pd.DataFrame, evidence_quality: pd.DataFrame,
                         target_size: int = TARGET_SAMPLE_SIZE,
                         seed: int = RANDOM_SEED) -> pd.DataFrame:
    """
    evidence_candidates: full behavioral_evidence_candidates.csv (discovery-derived
        already, since extraction only ever ran on the discovery split).
    evidence_quality: output of evidence_quality.assess_evidence_quality().
    """
    rng = np.random.RandomState(seed)
    merged = evidence_candidates.merge(evidence_quality, on="evidence_id", how="left")
    merged["confidence_band"] = merged.extractor_confidence.apply(_confidence_band)

    # Stratification dimensions, in priority order. We build the sample by drawing
    # a small, capped number from each (category x confidence_band x duplication_status)
    # cell, so no single dimension (or dominant duplicated phrase / application) can
    # take over the sample.
    merged["_strata_key"] = list(zip(
        merged.evidence_category, merged.confidence_band, merged.duplication_status,
    ))

    strata_groups = list(merged.groupby("_strata_key"))
    n_strata = len(strata_groups)
    # even-ish per-stratum cap, with a floor of 1 so rare strata still get represented
    per_stratum_cap = max(1, int(np.ceil(target_size / max(n_strata, 1))))

    # cap per-application and per-exact-span draws so one application or one repeated
    # phrase cannot dominate the sample
    MAX_PER_APPLICATION = 3
    MAX_PER_EXACT_SPAN = 4

    picked_rows = []
    app_counts = {}
    span_counts = {}

    # shuffle stratum order deterministically so no category is systematically favored
    order = list(range(n_strata))
    rng.shuffle(order)

    for idx in order:
        _, group = strata_groups[idx]
        group = group.sample(frac=1, random_state=seed)  # shuffle within stratum
        taken = 0
        for _, row in group.iterrows():
            if taken >= per_stratum_cap:
                break
            app_id = row.application_id
            span = row.evidence_span
            if app_counts.get(app_id, 0) >= MAX_PER_APPLICATION:
                continue
            if span_counts.get(span, 0) >= MAX_PER_EXACT_SPAN:
                continue
            picked_rows.append(row)
            app_counts[app_id] = app_counts.get(app_id, 0) + 1
            span_counts[span] = span_counts.get(span, 0) + 1
            taken += 1

    sample = pd.DataFrame(picked_rows)

    # If we came in under target (common, since caps are conservative), top up with
    # additional random draws respecting the same per-application/per-span caps,
    # prioritizing rows not yet included and favoring variety over volume.
    if len(sample) < target_size:
        remaining_pool = merged[~merged.evidence_id.isin(sample.evidence_id)].sample(
            frac=1, random_state=seed + 1
        )
        for _, row in remaining_pool.iterrows():
            if len(sample) >= target_size:
                break
            app_id = row.application_id
            span = row.evidence_span
            if app_counts.get(app_id, 0) >= MAX_PER_APPLICATION:
                continue
            if span_counts.get(span, 0) >= MAX_PER_EXACT_SPAN:
                continue
            sample = pd.concat([sample, row.to_frame().T], ignore_index=True)
            app_counts[app_id] = app_counts.get(app_id, 0) + 1
            span_counts[span] = span_counts.get(span, 0) + 1

    # Trim down if stratification overshot the target somewhat (allowed -- "approximately")
    if len(sample) > int(target_size * 1.15):
        sample = sample.sample(n=int(target_size * 1.1), random_state=seed)

    sample = sample.sort_values(["application_id", "timestamp"]).reset_index(drop=True)
    sample.insert(0, "review_sample_id", [f"REV-{i+1:04d}" for i in range(len(sample))])

    for col in ["human_decision", "human_evidence_category", "human_description", "human_notes"]:
        sample[col] = ""
    sample["human_decision"] = "PENDING"

    return sample[REVIEW_SAMPLE_COLUMNS]
