"""
application_behavior_builder.py -- Stage 7: Application x Behavior Bridge.

Builds application_behavior_mechanisms: exactly one row per
(application_id, mechanism_id), from human-APPROVED/EDITED mechanism mappings
only. NO_SUPPORTED_MECHANISM and any non-approved decision are excluded.
No evidence text or confidence is carried into this table by design -- it is
the CLEAN analytical bridge, not an evidence store.
"""
import pandas as pd

from .scenario_mapping import get_human_approved_mappings, mechanism_name_lookup

BRIDGE_COLUMNS = ["application_id", "mechanism_id", "mechanism_name"]

PROTECTED_SPLIT = "held_out_test"


def build_application_behavior_bridge(mapping_review_df: pd.DataFrame,
                                       applications_df: pd.DataFrame) -> pd.DataFrame:
    approved = get_human_approved_mappings(mapping_review_df)
    if len(approved) == 0:
        return pd.DataFrame(columns=BRIDGE_COLUMNS)

    mech_names = mechanism_name_lookup()
    app_split = applications_df.set_index("application_id")["research_split"]

    df = approved[["application_id", "effective_mechanism_id"]].rename(
        columns={"effective_mechanism_id": "mechanism_id"}
    )

    # research_split safeguard: defensively drop any held_out_test application,
    # even though evidence extraction structurally never touches that split today.
    df = df[df.application_id.map(app_split) != PROTECTED_SPLIT]

    # Deduplicate repeated evidence -- multiple approved evidence items mapping to
    # the same (application_id, mechanism_id) collapse to a single bridge row.
    df = df.drop_duplicates(subset=["application_id", "mechanism_id"]).reset_index(drop=True)

    df["mechanism_name"] = df["mechanism_id"].map(mech_names).fillna("")

    return df[BRIDGE_COLUMNS]
