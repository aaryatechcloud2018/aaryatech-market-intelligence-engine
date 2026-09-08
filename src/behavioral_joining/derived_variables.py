"""
derived_variables.py

Objective, non-behavioral derived variables only.

Explicitly OUT OF SCOPE here (by design, not oversight):
- behavioral mechanism labels
- risk scores
- joining probabilities
- psychological variables
- any behavioral "finding"

These are purely arithmetic/structural transformations of dates and counts that were
already present in the raw data.
"""
import pandas as pd

from .data_loader import BehavioralJoiningDataset

FORBIDDEN_COLUMN_SUBSTRINGS = [
    "risk_score", "risk", "probability", "prediction", "predicted",
    "mechanism", "behavioral_", "bias_", "psych",
]


def add_derived_variables(master: pd.DataFrame, ds: BehavioralJoiningDataset) -> pd.DataFrame:
    df = master.copy()

    df["days_application_to_interview"] = (df.interview_date - df.application_date).dt.days
    df["days_interview_to_offer"] = (df.offer_date - df.interview_date).dt.days
    df["days_offer_to_response"] = (df.offer_response_date - df.offer_date).dt.days
    df["days_acceptance_to_expected_start"] = (df.expected_start_date - df.offer_response_date).dt.days
    df["days_expected_to_actual_start"] = (df.actual_start_date - df.expected_start_date).dt.days

    df["pay_change_absolute"] = df.pay_rate_offered - df.pay_rate_prior
    df["pay_change_percentage"] = (
        (df.pay_rate_offered - df.pay_rate_prior) / df.pay_rate_prior.replace(0, pd.NA)
    ) * 100

    comm_counts = ds.communications.groupby("application_id").size().rename("total_communications")
    stage_counts = ds.stage_events.groupby("application_id").size().rename("total_stage_events")
    df = df.merge(comm_counts, on="application_id", how="left")
    df = df.merge(stage_counts, on="application_id", how="left")
    df["total_communications"] = df["total_communications"].fillna(0).astype(int)
    df["total_stage_events"] = df["total_stage_events"].fillna(0).astype(int)

    _assert_no_forbidden_columns(df)
    return df


def _assert_no_forbidden_columns(df: pd.DataFrame):
    for col in df.columns:
        low = col.lower()
        for bad in FORBIDDEN_COLUMN_SUBSTRINGS:
            if bad in low:
                raise ValueError(
                    f"Derived-variable safeguard triggered: column '{col}' matches forbidden "
                    f"pattern '{bad}'. Behavioral/risk/prediction variables are out of scope "
                    "for the data-foundation stage."
                )
