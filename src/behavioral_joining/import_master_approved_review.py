"""
import_master_approved_review.py

Imports the authoritative human-reviewed workbook
(Aaryatech_Behavioral_Review_MASTER_APPROVED.xlsx) into the EXISTING review
tables -- no parallel review architecture. Idempotent: matches on
evidence_id/review_sample_id and overwrites only those rows.

HUMAN_REVIEWED_NO_SUPPORTED_MECHANISM rows are preserved with
mapping_status=NO_SUPPORTED_MECHANISM and an empty mechanism_id, which is
exactly what the existing get_human_approved_mappings() filter (in
scenario_mapping.py) already excludes from downstream analysis -- no new
exclusion logic needed.
"""
from pathlib import Path
import openpyxl
import pandas as pd

from .mechanism_mapping import MAPPING_V2_COLUMNS
from .review_sampling import REVIEW_SAMPLE_COLUMNS

REVIEW_DIR = Path(__file__).resolve().parents[2] / "data" / "behavioral_joining" / "review"
WORKBOOK_PATH = REVIEW_DIR / "Aaryatech_Behavioral_Review_MASTER_APPROVED.xlsx"
SAMPLE_PATH = REVIEW_DIR / "evidence_human_review_sample.csv"
MAPPING_PATH = REVIEW_DIR / "mechanism_human_review.csv"


def _load_workbook_df() -> pd.DataFrame:
    wb = openpyxl.load_workbook(WORKBOOK_PATH, data_only=True)
    ws = wb["Behavioral Review"]
    data = list(ws.values)
    return pd.DataFrame(data[1:], columns=data[0])


def sync_evidence_review_sample(wb_df: pd.DataFrame) -> pd.DataFrame:
    sample = pd.read_csv(SAMPLE_PATH, keep_default_na=False)
    wb_idx = wb_df.set_index("review_sample_id")
    for i, row in sample.iterrows():
        rsid = row.review_sample_id
        if rsid in wb_idx.index:
            w = wb_idx.loc[rsid]
            sample.at[i, "human_decision"] = w.human_decision
            sample.at[i, "human_evidence_category"] = w.human_evidence_category or ""
            sample.at[i, "human_description"] = w.human_description or ""
            sample.at[i, "human_notes"] = w.human_notes or ""
    return sample[REVIEW_SAMPLE_COLUMNS]


def build_mechanism_review_from_workbook(wb_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, w in wb_df.iterrows():
        is_supported = w.behavioral_mapping_status == "HUMAN_APPROVED"
        rows.append({
            "mapping_id": f"MAP-{w.evidence_id}",
            "evidence_id": w.evidence_id,
            "application_id": w.application_id,
            "mechanism_id": w.proposed_behavioral_mechanism_id if is_supported else "",
            "mechanism_name": w.proposed_behavioral_mechanism_name if is_supported else "",
            "mapping_reason": w.behavioral_mapping_reason or "",
            "supporting_context": "",
            "contradictory_context": "",
            "mapping_confidence": w.behavioral_mapping_confidence,
            "alternative_mechanism_id": "",
            "alternative_reason": w.alternative_behavioral_interpretation or "",
            "mapping_status": "PROPOSED" if is_supported else "NO_SUPPORTED_MECHANISM",
            "human_mapping_decision": w.human_decision,  # APPROVE for both, per workbook
            "human_selected_mechanism": "",
            "human_mapping_notes": "Imported from Aaryatech_Behavioral_Review_MASTER_APPROVED.xlsx",
        })
    return pd.DataFrame(rows, columns=MAPPING_V2_COLUMNS)


def run_import():
    wb_df = _load_workbook_df()
    n_total = len(wb_df)
    n_approved = (wb_df.behavioral_mapping_status == "HUMAN_APPROVED").sum()
    n_no_supported = (wb_df.behavioral_mapping_status == "HUMAN_REVIEWED_NO_SUPPORTED_MECHANISM").sum()
    n_pending = (wb_df.human_decision == "PENDING").sum()

    updated_sample = sync_evidence_review_sample(wb_df)
    updated_sample.to_csv(SAMPLE_PATH, index=False)

    mapping_review = build_mechanism_review_from_workbook(wb_df)
    mapping_review.to_csv(MAPPING_PATH, index=False)

    return {
        "total_rows": n_total,
        "approved_supported": int(n_approved),
        "no_supported_mechanism": int(n_no_supported),
        "pending": int(n_pending),
        "unique_applications": wb_df.application_id.nunique(),
    }


if __name__ == "__main__":
    print(run_import())
