"""
behavior_outcome_builder.py -- Stage 8: Behavior x Outcome Dataset.

Joins application_behavior_mechanisms to candidate outcomes. STRICT RULE:
only discovery and hypothesis_generation splits may enter this dataset.
held_out_test is hard-blocked, not just filtered -- see
assert_no_held_out_leakage() below, which is called unconditionally before
returning any result.

No statistical testing happens in this module -- that is Stage 10/11's job.
"""
import pandas as pd

ALLOWED_SPLITS = {"discovery", "hypothesis_generation"}
PROTECTED_SPLIT = "held_out_test"

OUTCOME_COLUMNS = [
    "application_id", "mechanism_id", "mechanism_name", "research_split",
    "final_disposition", "job_family", "client_account_id", "recruiter_id",
]


class HeldOutLeakageError(RuntimeError):
    pass


def assert_no_held_out_leakage(df: pd.DataFrame):
    if "research_split" not in df.columns:
        raise HeldOutLeakageError("behavior_outcome_dataset is missing research_split -- cannot verify safeguard.")
    if (df.research_split == PROTECTED_SPLIT).any():
        raise HeldOutLeakageError(
            f"{(df.research_split == PROTECTED_SPLIT).sum()} held_out_test rows were about to enter "
            "behavior_outcome_dataset. This is a hard stop."
        )


def build_behavior_outcome_dataset(bridge_df: pd.DataFrame, applications_df: pd.DataFrame) -> pd.DataFrame:
    if len(bridge_df) == 0:
        result = pd.DataFrame(columns=OUTCOME_COLUMNS)
        assert_no_held_out_leakage(result)
        return result

    apps = applications_df[applications_df.research_split.isin(ALLOWED_SPLITS)][
        ["application_id", "research_split", "final_disposition", "job_family", "client_account_id", "recruiter_id"]
    ]

    merged = bridge_df.merge(apps, on="application_id", how="inner")
    # inner join: this IS the safeguard, expressed structurally -- any bridge row
    # whose application isn't in the allowed-split set is silently dropped.

    result = merged[OUTCOME_COLUMNS].reset_index(drop=True)
    assert_no_held_out_leakage(result)
    return result
