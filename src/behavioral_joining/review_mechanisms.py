"""
review_mechanisms.py

Run with:
    python -m src.behavioral_joining.review_mechanisms

Terminal review tool for mechanism_human_review.csv. Saves after every decision.
"""
from pathlib import Path
import json
import sys
import pandas as pd

REVIEW_DIR = Path(__file__).resolve().parents[2] / "data" / "behavioral_joining" / "review"
MAPPING_PATH = REVIEW_DIR / "mechanism_human_review.csv"
LIBRARY_PATH = Path(__file__).resolve().parents[2] / "data" / "behavioral_joining" / "reference" / "behavioral_mechanisms.json"


def _load_library_lookup():
    if not LIBRARY_PATH.exists():
        return {}
    data = json.loads(LIBRARY_PATH.read_text())
    return {m["Pattern_ID"]: m for m in data.get("mechanisms", [])}


def _load():
    if not MAPPING_PATH.exists():
        print(f"No mechanism mapping file found at {MAPPING_PATH}.")
        print("Run: python -m src.behavioral_joining.run_mechanism_mapping first.")
        sys.exit(1)
    return pd.read_csv(MAPPING_PATH, keep_default_na=False)


def _save(df):
    df.to_csv(MAPPING_PATH, index=False)


def _display(row, idx, total, lib_lookup):
    print("\n" + "=" * 78)
    print(f"Mapping {idx + 1} of {total}   (mapping_id: {row.mapping_id})")
    print("=" * 78)
    print(f"Evidence ID:      {row.evidence_id}")
    print(f"Application:      {row.application_id}")
    print(f"Status:           {row.mapping_status}")
    print()
    if row.mapping_status == "NO_SUPPORTED_MECHANISM":
        print("AI found no supported mechanism for this evidence.")
        print(f"Reason: {row.mapping_reason}")
    else:
        mech = lib_lookup.get(row.mechanism_id, {})
        print(f"AI-proposed mechanism: {row.mechanism_id} - {row.mechanism_name}")
        if mech:
            print(f"  Definition:            {mech.get('Simple_Definition','')}")
            print(f"  Evidence requirements: {mech.get('Evidence_Requirements','')}")
        print(f"  Mapping reason:        {row.mapping_reason}")
        print(f"  Supporting context:    {row.supporting_context}")
        print(f"  Contradictory context: {row.contradictory_context}")
        print(f"  Confidence:            {row.mapping_confidence}")
        if row.alternative_mechanism_id:
            print(f"  Alternative mechanism: {row.alternative_mechanism_id} - "
                  f"{row.alternative_reason}")
    print()


def _prompt_action():
    return input("[A]pprove / [E]dit-mechanism / [R]eject / "
                 "[N]confirm-no-mechanism / [S]kip / [Q]uit-and-save: ").strip().upper()


def run_review():
    df = _load()
    lib_lookup = _load_library_lookup()
    total = len(df)
    n_pending = (df.human_mapping_decision == "PENDING").sum()
    print(f"Loaded {total} mapping records ({n_pending} still pending).")

    for idx, row in df.iterrows():
        if row.human_mapping_decision != "PENDING":
            continue
        _display(row, idx, total, lib_lookup)
        action = _prompt_action()

        if action == "Q":
            print("Saving progress and exiting.")
            break
        elif action == "S":
            continue
        elif action == "A":
            df.at[idx, "human_mapping_decision"] = "APPROVE"
            df.at[idx, "human_selected_mechanism"] = row.mechanism_id
            notes = input("Optional notes: ").strip()
            df.at[idx, "human_mapping_notes"] = notes
            _save(df)
            print("Saved: APPROVED.")
        elif action == "N":
            df.at[idx, "human_mapping_decision"] = "APPROVE"
            df.at[idx, "human_selected_mechanism"] = ""
            notes = input("Optional notes on why no mechanism applies: ").strip()
            df.at[idx, "human_mapping_notes"] = notes or "Confirmed: no supported mechanism."
            _save(df)
            print("Saved: NO_SUPPORTED_MECHANISM confirmed.")
        elif action == "R":
            reason = input("Reason for rejection: ").strip()
            df.at[idx, "human_mapping_decision"] = "REJECT"
            df.at[idx, "human_mapping_notes"] = reason
            _save(df)
            print("Saved: REJECTED.")
        elif action == "E":
            new_mech = input(f"New mechanism ID (e.g. BM-012) [{row.mechanism_id}]: ").strip() \
                or row.mechanism_id
            notes = input("Reasoning for this change: ").strip()
            df.at[idx, "human_mapping_decision"] = "EDIT"
            df.at[idx, "human_selected_mechanism"] = new_mech
            df.at[idx, "human_mapping_notes"] = notes
            _save(df)
            print("Saved: EDITED.")
        else:
            print("Not recognized -- treating as skip.")
            continue

    remaining = (df.human_mapping_decision == "PENDING").sum()
    print(f"\nDone for now. {remaining} mapping records still pending out of {total}.")
    print("Run this command again any time to continue where you left off.")


if __name__ == "__main__":
    run_review()
