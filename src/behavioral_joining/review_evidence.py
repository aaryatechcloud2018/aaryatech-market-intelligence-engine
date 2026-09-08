"""
review_evidence.py

Simple terminal review tool for the human evidence review sample. No new
dependencies -- plain Python input(), plain CSV read/write.

Run with:
    python -m src.behavioral_joining.review_evidence

Saves after every single decision, so progress is never lost even if you stop
partway through.
"""
from pathlib import Path
import sys
import pandas as pd

from .review_sampling import REVIEW_SAMPLE_COLUMNS

REVIEW_DIR = Path(__file__).resolve().parents[2] / "data" / "behavioral_joining" / "review"
SAMPLE_PATH = REVIEW_DIR / "evidence_human_review_sample.csv"


def _load():
    if not SAMPLE_PATH.exists():
        print(f"Review sample not found at {SAMPLE_PATH}.")
        print("Run the main pipeline first to generate it.")
        sys.exit(1)
    return pd.read_csv(SAMPLE_PATH, keep_default_na=False)


def _save(df):
    df.to_csv(SAMPLE_PATH, index=False)


def _display(row, idx, total):
    print("\n" + "=" * 78)
    print(f"Record {idx + 1} of {total}   (review_sample_id: {row.review_sample_id})")
    print("=" * 78)
    print(f"Application:      {row.application_id}")
    print(f"Source:           {row.source_type} ({row.direction})")
    print(f"Timestamp:        {row.timestamp}")
    print(f"Response latency: {row.response_latency_hours} hours")
    print()
    if row.context_before:
        print(f"  ...before: \"{row.context_before}\"")
    print(f"  >>> EVIDENCE: \"{row.evidence_span}\"")
    if row.context_after:
        print(f"  ...after:  \"{row.context_after}\"")
    print()
    print(f"Proposed category:    {row.evidence_category}")
    print(f"Proposed description: {row.evidence_description}")
    print(f"Extractor confidence: {row.extractor_confidence}")
    print(f"Quality flags:        information={row.information_quality}, "
          f"duplication={row.duplication_status}")
    print()


def _prompt_action():
    return input("[A]pprove / [E]dit / [R]eject / [S]kip / [Q]uit-and-save: ").strip().upper()


def run_review():
    df = _load()
    total = len(df)
    n_pending = (df.human_decision == "PENDING").sum()
    print(f"Loaded {total} review records ({n_pending} still pending).")

    for idx, row in df.iterrows():
        if row.human_decision != "PENDING":
            continue
        _display(row, idx, total)
        action = _prompt_action()

        if action == "Q":
            print("Saving progress and exiting.")
            break
        elif action == "S":
            continue
        elif action == "A":
            df.at[idx, "human_decision"] = "APPROVE"
            df.at[idx, "human_evidence_category"] = row.evidence_category
            df.at[idx, "human_description"] = row.evidence_description
            notes = input("Optional notes (press Enter to skip): ").strip()
            df.at[idx, "human_notes"] = notes
            _save(df)
            print("Saved: APPROVED.")
        elif action == "R":
            reason = input("Reason for rejection (optional): ").strip()
            df.at[idx, "human_decision"] = "REJECT"
            df.at[idx, "human_notes"] = reason
            _save(df)
            print("Saved: REJECTED.")
        elif action == "E":
            new_cat = input(f"New category [{row.evidence_category}]: ").strip() or row.evidence_category
            new_desc = input(f"New description [{row.evidence_description}]: ").strip() or row.evidence_description
            notes = input("Notes on this edit (optional): ").strip()
            df.at[idx, "human_decision"] = "EDIT"
            df.at[idx, "human_evidence_category"] = new_cat
            df.at[idx, "human_description"] = new_desc
            df.at[idx, "human_notes"] = notes
            _save(df)
            print("Saved: EDITED.")
        else:
            print("Not recognized -- treating as skip.")
            continue

    remaining = (df.human_decision == "PENDING").sum()
    print(f"\nDone for now. {remaining} records still pending out of {total}.")
    print("Run this command again any time to continue where you left off.")

    # Regenerate the progress report every time this tool runs, per spec.
    from .review_progress_report import write_human_review_progress_report
    write_human_review_progress_report(df)


if __name__ == "__main__":
    run_review()
