"""
run_mechanism_mapping.py

Run with:
    python -m src.behavioral_joining.run_mechanism_mapping

Maps ONLY evidence where human_decision is APPROVE or EDIT in
evidence_human_review_sample.csv. PENDING and REJECT rows are never mapped -- this
is enforced in code, not just by convention (see the hard filter below).

Loads ONLY the frozen source-of-truth library at
data/behavioral_joining/reference/behavioral_mechanisms.json, and never writes to it.

If nobody has approved/edited anything yet, this creates the (empty) output file
with the correct schema and says so plainly -- it does not fabricate approvals.
"""
from pathlib import Path
import pandas as pd

from .mechanism_library import load_mechanism_library
from .mechanism_mapping import map_reviewed_evidence, MAPPING_V2_COLUMNS

REVIEW_DIR = Path(__file__).resolve().parents[2] / "data" / "behavioral_joining" / "review"
SAMPLE_PATH = REVIEW_DIR / "evidence_human_review_sample.csv"
OUTPUT_PATH = REVIEW_DIR / "mechanism_human_review.csv"

VALID_HUMAN_DECISIONS_FOR_MAPPING = {"APPROVE", "EDIT"}


def run():
    print("=" * 70)
    print("Behavioral Mechanism Mapping -- human-approved evidence only")
    print("=" * 70)

    if not SAMPLE_PATH.exists():
        print(f"No review sample found at {SAMPLE_PATH}. Run the main pipeline first.")
        return

    sample = pd.read_csv(SAMPLE_PATH, keep_default_na=False)
    approved = sample[sample.human_decision.isin(VALID_HUMAN_DECISIONS_FOR_MAPPING)].copy()

    print(f"Review sample: {len(sample)} rows total.")
    print(f"Eligible for mapping (APPROVE or EDIT only): {len(approved)} rows.")
    if len(approved) == 0:
        print("\nNo evidence has been approved or edited yet -- nothing to map.")
        print("This is expected if human review hasn't started. Writing an empty, "
              "correctly-structured output file rather than fabricating anything.")
        empty = pd.DataFrame(columns=MAPPING_V2_COLUMNS)
        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        empty.to_csv(OUTPUT_PATH, index=False)
        print(f"Saved: {OUTPUT_PATH} (0 rows)")
        return

    # Use the human-edited category/description when present, since that reflects
    # the analyst's final judgment, not the AI's original proposal.
    approved["human_evidence_category"] = approved["human_evidence_category"].where(
        approved["human_evidence_category"].astype(str).str.len() > 0, approved["evidence_category"]
    )

    lib = load_mechanism_library()
    print(f"\nMechanism library status: {lib.status}")
    if lib.status == "LOADED":
        print(f"Loaded {len(lib.mechanisms)} mechanisms from {lib.source_path}")
    else:
        print(f"NOT LOADED: {lib.error}")

    mappings = map_reviewed_evidence(approved, lib)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    mappings.to_csv(OUTPUT_PATH, index=False)

    n_proposed = (mappings.mapping_status == "PROPOSED").sum()
    n_none = (mappings.mapping_status == "NO_SUPPORTED_MECHANISM").sum()
    print(f"\nMapping records created: {len(mappings)}")
    print(f"  PROPOSED: {n_proposed}")
    print(f"  NO_SUPPORTED_MECHANISM: {n_none}")
    print(f"Saved: {OUTPUT_PATH}")
    print("\nAll mappings start human_mapping_decision = PENDING.")
    print("Next: python -m src.behavioral_joining.review_mechanisms")


if __name__ == "__main__":
    run()
