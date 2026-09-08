"""
run_behavioral_pipeline.py

One-command orchestrator. Run with:

    python -m src.behavioral_joining.run_behavioral_pipeline

Prints plain-language progress for each stage. Stops before any held-out analysis --
that code path is never called from here. Never runs the interactive review tools
(review_evidence.py / run_mechanism_mapping.py / review_mechanisms.py) itself --
those require a human and are separate commands by design.
"""
from pathlib import Path
import sys
import pandas as pd

from .data_loader import RAW_DIR
from .discovery_context import build_discovery_working_set
from .build_journey_master import build_master
from .evidence_extraction import extract_evidence
from .objective_signals import compute_objective_signals
from .evidence_review import initialize_review_file
from .evidence_quality import assess_evidence_quality
from .review_sampling import build_review_sample, REVIEW_SAMPLE_COLUMNS
from .mechanism_library import load_mechanism_library
from .mechanism_mapping import map_mechanism, MAPPING_V2_COLUMNS
from .mechanism_mapping_review import initialize_mapping_review_file
from .calibration_metrics import (
    compute_evidence_agreement_metrics, compute_mechanism_agreement_metrics, write_calibration_report,
)
from .hypothesis_readiness import compute_hypothesis_readiness, READINESS_COLUMNS
from .review_progress_report import write_human_review_progress_report
from .database import build_database, populate_database, table_row_counts, DB_PATH

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "behavioral_joining" / "processed"
REVIEW_DIR = Path(__file__).resolve().parents[2] / "data" / "behavioral_joining" / "review"
REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports" / "behavioral_joining"


def _print_stage(n, total, message):
    print(f"\n[Step {n}/{total}] {message}")


def run_pipeline():
    total_steps = 12
    print("=" * 70)
    print("Aaryatech Behavioral Joining Intelligence -- Pipeline Run")
    print("=" * 70)
    print("This tool prepares behavioral EVIDENCE for human review. It does not")
    print("score, rank, or predict anything about any candidate.")

    # 1. Loading validated data
    _print_stage(1, total_steps, "Loading validated data (candidate_journey_master.csv, "
                                  "communications, stage events)...")
    master = build_master(RAW_DIR)
    print(f"   Loaded {len(master)} candidate applications.")

    # 2. Building discovery working set
    _print_stage(2, total_steps, "Building the DISCOVERY-only working set (outcome hidden)...")
    ctx = build_discovery_working_set(RAW_DIR)
    print(f"   Using {ctx.n_discovery_applications} of {ctx.n_total_applications} applications "
          f"(the 'discovery' research split only).")
    print("   Outcome fields (final_disposition, disposition_date, actual_start_date) have "
          "been removed from what the extractor can see.")

    # 3. Extracting behavioral evidence
    _print_stage(3, total_steps, "Extracting behavioral evidence from communications...")
    evidence_candidates = extract_evidence(ctx)
    print(f"   Proposed {len(evidence_candidates)} evidence candidates across "
          f"{evidence_candidates.evidence_category.nunique()} categories.")
    print("   Every item is marked 'pending' -- nothing is auto-approved.")

    signals = compute_objective_signals(ctx)
    print(f"   Also computed {signals.shape[1] - 1} objective communication/process "
          f"observations for {len(signals)} applications (counts and gaps only, no scores).")

    # 4. Creating human review file (full ledger -- Task 2-5 lineage, kept for continuity)
    _print_stage(4, total_steps, "Creating the full evidence review ledger...")
    evidence_review = initialize_review_file(evidence_candidates)
    evidence_candidates.to_csv(PROCESSED_DIR / "behavioral_evidence_candidates.csv", index=False)
    evidence_review.to_csv(PROCESSED_DIR / "behavioral_evidence_review.csv", index=False)
    print(f"   Saved: {PROCESSED_DIR / 'behavioral_evidence_candidates.csv'} ({len(evidence_candidates)} rows)")
    print(f"   Saved: {PROCESSED_DIR / 'behavioral_evidence_review.csv'} ({len(evidence_review)} rows)")

    # 5. Evidence quality cleanup
    _print_stage(5, total_steps, "Assessing evidence quality (duplication, information quality)...")
    evidence_quality = assess_evidence_quality(evidence_candidates)
    evidence_quality.to_csv(PROCESSED_DIR / "behavioral_evidence_quality.csv", index=False)
    print(f"   Saved: {PROCESSED_DIR / 'behavioral_evidence_quality.csv'} ({len(evidence_quality)} rows)")
    print(f"   Duplication status breakdown: "
          f"{dict(evidence_quality.duplication_status.value_counts())}")

    # 6. Building the ~250-row stratified human review sample (idempotent)
    _print_stage(6, total_steps, "Preparing the human review sample (~250 rows, stratified)...")
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    sample_path = REVIEW_DIR / "evidence_human_review_sample.csv"
    if sample_path.exists():
        review_sample = pd.read_csv(sample_path, keep_default_na=False)
        print(f"   Review sample already exists ({len(review_sample)} rows) -- NOT regenerated, "
              f"to avoid losing any review progress already saved.")
    else:
        review_sample = build_review_sample(evidence_candidates, evidence_quality)
        review_sample.to_csv(sample_path, index=False)
        print(f"   Created: {sample_path} ({len(review_sample)} rows, "
              f"{review_sample.application_id.nunique()} distinct applications, "
              f"{review_sample.evidence_category.nunique()} categories represented)")
    n_pending = (review_sample.human_decision == "PENDING").sum()
    print(f"   Run 'python -m src.behavioral_joining.review_evidence' to review "
          f"({n_pending} pending).")

    # 7. Loading 34-mechanism library
    _print_stage(7, total_steps, "Loading the frozen 34-mechanism behavioral library...")
    lib_result = load_mechanism_library()
    if lib_result.status == "LOADED":
        print(f"   Loaded {len(lib_result.mechanisms)} mechanisms from {lib_result.source_path}")
    else:
        print(f"   NOT LOADED: {lib_result.error}")

    # 8. Mechanism mapping scaffolding (only real for APPROVE/EDIT rows; empty otherwise)
    _print_stage(8, total_steps, "Preparing mechanism mapping scaffolding (human-approved evidence only)...")
    approved_sample_rows = review_sample[review_sample.human_decision.isin(["APPROVE", "EDIT"])]
    print(f"   {len(approved_sample_rows)} of {len(review_sample)} review-sample rows are "
          f"currently APPROVE/EDIT (0 is expected until human review begins).")
    mapping_path = REVIEW_DIR / "mechanism_human_review.csv"
    if mapping_path.exists():
        mapping_review_v2 = pd.read_csv(mapping_path, keep_default_na=False)
        print(f"   mechanism_human_review.csv already exists ({len(mapping_review_v2)} rows) -- "
              f"NOT regenerated, to avoid losing review progress. Run "
              f"'python -m src.behavioral_joining.run_mechanism_mapping' to add newly-approved evidence.")
    else:
        if len(approved_sample_rows):
            from .mechanism_mapping import map_reviewed_evidence
            mapping_review_v2 = map_reviewed_evidence(approved_sample_rows, lib_result)
        else:
            mapping_review_v2 = pd.DataFrame(columns=MAPPING_V2_COLUMNS)
        mapping_review_v2.to_csv(mapping_path, index=False)
        print(f"   Created: {mapping_path} ({len(mapping_review_v2)} rows) -- "
              f"WAITING FOR HUMAN REVIEW of evidence before this has real content.")

    # legacy Task 2-5 mechanism mapping pass (kept for continuity/backward compatibility)
    approved_evidence_legacy = evidence_review[evidence_review.review_decision.isin(["approved", "edited"])]
    approved_evidence_legacy_full = evidence_candidates[
        evidence_candidates.evidence_id.isin(approved_evidence_legacy.evidence_id)
    ]
    mapping_candidates = map_mechanism(approved_evidence_legacy_full, lib_result)
    mapping_review = initialize_mapping_review_file(mapping_candidates) if len(mapping_candidates) else \
        pd.DataFrame(columns=["mapping_id", "evidence_id", "application_id", "original_mechanism_id",
                               "original_mechanism_name", "original_mapping_reason",
                               "original_evidence_support_level", "original_mapping_confidence",
                               "review_decision", "edited_mechanism_id", "edited_mechanism_name",
                               "added_alternative_interpretation", "reviewer", "review_timestamp",
                               "reviewer_notes"])
    mapping_candidates.to_csv(PROCESSED_DIR / "mechanism_mapping_candidates.csv", index=False)
    mapping_review.to_csv(PROCESSED_DIR / "mechanism_mapping_review.csv", index=False)

    # 9. Calibration metrics + hypothesis readiness
    _print_stage(9, total_steps, "Computing calibration metrics and hypothesis readiness...")
    evidence_metrics = compute_evidence_agreement_metrics(review_sample)
    mechanism_metrics = compute_mechanism_agreement_metrics(mapping_review_v2)
    write_calibration_report(evidence_metrics, mechanism_metrics)
    if evidence_metrics["status"] == "no_reviews_yet":
        print("   Evidence calibration: WAITING FOR HUMAN REVIEW.")
    else:
        print(f"   Evidence calibration computed from {evidence_metrics['n_reviewed']} reviewed rows.")

    readiness = compute_hypothesis_readiness(mapping_review_v2, evidence_quality)
    readiness.to_csv(PROCESSED_DIR / "hypothesis_readiness.csv", index=False)
    if len(readiness) == 0:
        print("   Hypothesis readiness: WAITING FOR HUMAN REVIEW (0 approved mappings so far).")
    else:
        n_ready = readiness.ready_for_hypothesis_generation.sum()
        print(f"   Hypothesis readiness computed for {len(readiness)} mechanisms; {n_ready} currently "
              f"meet MVP development thresholds (not scientific validation).")

    write_human_review_progress_report(review_sample)

    # 10. Updating SQLite database
    _print_stage(10, total_steps, "Updating the SQLite database (database/behavioral_joining.db)...")
    from .data_loader import load_dataset
    ds = load_dataset(RAW_DIR)
    build_database(DB_PATH)
    populate_database(DB_PATH, {
        "bj_candidate_journey": master.drop(columns=[c for c in master.columns if c not in [
            "application_id", "candidate_id", "requisition_id", "client_account_id", "recruiter_id",
            "job_title", "job_family", "location_city", "location_state", "work_arrangement",
            "contract_type", "years_experience", "application_source", "pay_rate_prior",
            "pay_rate_offered", "notice_period_days", "application_date", "interview_date",
            "offer_date", "offer_response_date", "expected_start_date", "actual_start_date",
            "offer_extended", "offer_accepted", "final_disposition", "disposition_date", "research_split",
        ]]),
        "bj_communication_log": ds.communications,
        "bj_stage_events": ds.stage_events,
        "bj_clients": ds.clients,
        "bj_recruiters": ds.recruiters,
        "bj_requisitions": ds.requisitions,
        "bj_evidence_candidates": evidence_candidates,
        "bj_evidence_review": evidence_review,
        "bj_mechanism_mapping_candidates": mapping_candidates,
        "bj_mechanism_mapping_review": mapping_review,
        "bj_evidence_quality": evidence_quality,
        "bj_evidence_review_sample": review_sample,
        "bj_mechanism_review": mapping_review_v2,
        "bj_hypothesis_readiness": readiness,
    }, mechanism_library_result=lib_result)
    counts = table_row_counts(DB_PATH)
    for t, c in counts.items():
        print(f"     {t}: {c} rows")

    # 11. Generating QA reports
    _print_stage(11, total_steps, "Generating QA reports...")
    from .generate_validation_report import generate_report
    generate_report()
    from .evidence_extraction_report import write_evidence_extraction_report
    write_evidence_extraction_report(evidence_candidates, signals, ctx)
    from .mechanism_mapping_report import write_mechanism_mapping_report
    write_mechanism_mapping_report(mapping_candidates, lib_result)
    from .behavioral_engine_status_report import write_status_report
    write_status_report(evidence_candidates, evidence_review, mapping_candidates, mapping_review,
                         lib_result, counts)
    print(f"   Reports saved under: {REPORTS_DIR}")

    # 12. Running tests/safeguards, then stopping
    _print_stage(12, total_steps, "Running automated tests and safeguards, then stopping...")
    import subprocess
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q"],
                             cwd=str(Path(__file__).resolve().parents[2]),
                             capture_output=True, text=True)
    print(result.stdout[-1500:])
    if result.returncode != 0:
        print("   TESTS FAILED. Please review before trusting these outputs.")
    else:
        print("   All tests passed.")

    print("\n   held_out_test data has NOT been inspected or used at any point in this run.")
    print("   08_scenario_ground_truth.csv has NOT been loaded at any point in this run.")
    print("   No behavioral finding has been claimed or statistically validated.")
    print("\nNext step is human review:")
    print("   python -m src.behavioral_joining.review_evidence")
    print("=" * 70)


if __name__ == "__main__":
    run_pipeline()
