"""
build_journey_master.py

Builds candidate_journey_master.csv: one row per application/candidate journey,
merging structured fields from applications + requisitions + clients + recruiters.

Explicitly does NOT flatten communication_log or stage_events into this table --
those remain separate because timing and sequence within them are themselves
behavioral evidence that would be destroyed by flattening to one row per application.
"""
from pathlib import Path
import pandas as pd

from .data_loader import load_dataset, RAW_DIR
from .derived_variables import add_derived_variables

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "behavioral_joining" / "processed"


def build_master(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    ds = load_dataset(raw_dir)

    apps = ds.applications
    reqs = ds.requisitions.add_prefix("req_").rename(columns={"req_requisition_id": "requisition_id"})
    clients = ds.clients.add_prefix("client_").rename(columns={"client_client_account_id": "client_account_id"})
    recruiters = ds.recruiters.add_prefix("recruiter_").rename(columns={"recruiter_recruiter_id": "recruiter_id"})

    # Columns that are duplicated between applications and requisitions (job_title,
    # job_family, location, work_arrangement, contract_type) -- applications already
    # carries the effective values used for that specific candidate journey, so we
    # keep the applications version and drop the requisition duplicates rather than
    # creating redundant *_x / *_y columns.
    req_drop_cols = ["req_job_title", "req_job_family", "req_location_city",
                      "req_location_state", "req_work_arrangement", "req_contract_type",
                      "req_client_account_id"]
    reqs_slim = reqs.drop(columns=[c for c in req_drop_cols if c in reqs.columns])

    master = apps.merge(reqs_slim, on="requisition_id", how="left")
    master = master.merge(clients, on="client_account_id", how="left")
    master = master.merge(recruiters, on="recruiter_id", how="left")

    # client_primary_job_families duplicates info already reflected per-application
    # in job_family; keep it (it describes the client's general focus, not this
    # specific journey) but rename for clarity.
    master = master.rename(columns={"client_primary_job_families": "client_primary_job_families_general"})

    master = add_derived_variables(master, ds)

    # Column ordering: keep IDs and outcome fields up front for readability.
    front_cols = [
        "application_id", "candidate_id", "requisition_id", "client_account_id", "recruiter_id",
        "job_title", "job_family", "location_city", "location_state", "work_arrangement",
        "contract_type", "years_experience", "application_source",
        "pay_rate_prior", "pay_rate_offered", "notice_period_days",
        "application_date", "interview_date", "offer_date", "offer_response_date",
        "expected_start_date", "actual_start_date",
        "offer_extended", "offer_accepted", "final_disposition", "disposition_date",
        "research_split",
    ]
    other_cols = [c for c in master.columns if c not in front_cols]
    master = master[front_cols + other_cols]

    return master


def save_master(master: pd.DataFrame, out_dir: Path = PROCESSED_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "candidate_journey_master.csv"
    master.to_csv(out_path, index=False)
    return out_path


if __name__ == "__main__":
    master = build_master()
    path = save_master(master)
    print(f"candidate_journey_master.csv written: {path}")
    print(f"Shape: {master.shape[0]} rows x {master.shape[1]} columns")
