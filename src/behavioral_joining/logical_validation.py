"""
logical_validation.py

Logical / cross-field consistency checks for the behavioral_joining dataset.
Reports problems; does not silently fix anything.
"""
import pandas as pd

from .data_loader import BehavioralJoiningDataset
from .schema_validation import ValidationResult


def validate_logic(ds: BehavioralJoiningDataset) -> ValidationResult:
    result = ValidationResult(passed=True)
    apps = ds.applications.copy()
    comms = ds.communications.copy()
    stages = ds.stage_events.copy()

    # --- actual_start_date must be null for accepted_no_show, withdrew_post_acceptance, declined_offer
    null_required = ["accepted_no_show", "withdrew_post_acceptance", "declined_offer"]
    bad = apps[apps.final_disposition.isin(null_required) & apps.actual_start_date.notna()]
    if len(bad):
        result.add_error(
            f"{len(bad)} rows in {null_required} have a non-null actual_start_date "
            f"(application_ids: {bad.application_id.head(5).tolist()}{'...' if len(bad) > 5 else ''})"
        )

    # --- offer_accepted must be TRUE for these dispositions
    true_required = ["joined_on_time", "joined_late", "accepted_no_show", "withdrew_post_acceptance"]
    for disp in true_required:
        bad = apps[(apps.final_disposition == disp) & (apps.offer_accepted != True)]
        if len(bad):
            result.add_error(f"{len(bad)} '{disp}' rows have offer_accepted != True")

    # --- offer_accepted must be FALSE for declined_offer
    bad = apps[(apps.final_disposition == "declined_offer") & (apps.offer_accepted != False)]
    if len(bad):
        result.add_error(f"{len(bad)} 'declined_offer' rows have offer_accepted != False")

    # --- expected_start_date must not occur before offer acceptance (offer_response_date)
    bad = apps[apps.expected_start_date < apps.offer_response_date]
    if len(bad):
        result.add_error(f"{len(bad)} rows have expected_start_date before offer_response_date")

    # --- actual_start_date must not occur before expected_start_date for joined_late
    bad = apps[(apps.final_disposition == "joined_late") &
               (apps.actual_start_date < apps.expected_start_date)]
    if len(bad):
        result.add_error(f"{len(bad)} 'joined_late' rows have actual_start_date before expected_start_date")

    # --- joined_on_time should have actual_start_date reasonably close to expected_start_date
    jot = apps[apps.final_disposition == "joined_on_time"]
    dev = (jot.actual_start_date - jot.expected_start_date).abs().dt.days
    bad = jot[dev > 1]
    if len(bad):
        result.add_warning(f"{len(bad)} 'joined_on_time' rows deviate more than 1 day from expected_start_date")

    # --- application < interview < offer < offer_response chronology
    bad = apps[~((apps.application_date <= apps.interview_date) &
                 (apps.interview_date <= apps.offer_date) &
                 (apps.offer_date <= apps.offer_response_date))]
    if len(bad):
        result.add_error(f"{len(bad)} rows violate application < interview < offer < offer_response chronology")

    # --- communication timestamps cannot precede the application/candidate journey
    comm_check = comms.merge(
        apps[["application_id", "application_date", "disposition_date"]],
        on="application_id", how="left"
    )
    bad = comm_check[comm_check.timestamp < comm_check.application_date]
    if len(bad):
        result.add_error(f"{len(bad)} communication records occur before their application's application_date")

    unresolved = comm_check[comm_check.application_date.isna()]
    if len(unresolved):
        result.add_error(f"{len(unresolved)} communication records reference an application_id not found in applications")

    # --- stage timestamps chronologically plausible within each application
    bad_apps = 0
    for app_id, sub in stages.sort_values(["application_id", "stage_timestamp"]).groupby("application_id"):
        diffs = sub.stage_timestamp.diff().dropna()
        if (diffs.dt.days < 0).any():
            bad_apps += 1
    if bad_apps:
        result.add_error(f"{bad_apps} applications have out-of-order stage_event timestamps")

    # --- no duplicate primary IDs (cross-check with schema_validation, kept here too since
    #     the spec explicitly lists it under logical validation)
    for name, pk in [("applications", "application_id"), ("communications", "log_id"),
                      ("stage_events", "event_id")]:
        df = getattr(ds, name)
        n_dup = df[pk].duplicated().sum()
        if n_dup:
            result.add_error(f"[{name}] {n_dup} duplicate '{pk}' values")

    return result
