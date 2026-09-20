"""
hypothesis_engine.py

Generates falsifiable behavioral hypothesis RECORDS from the behavior x outcome
dataset (Stage 8), optionally enriched with the client scenario library (Stage 6).
Both of those inputs already trace back to human-approved evidence and
human-approved mechanism mappings only -- nothing here bypasses that gate.

Schema updated (Stage 9, Master Code Guide Section 6) to include scenario_id,
journey_stage, segment, sample_size, discovery_dataset_reference, created_date,
tested_date, and validation_status, and to use the full required status
vocabulary. This is a modification of the existing engine, not a replacement --
the module purpose, the "no fabricated hypotheses" behavior, and
demo_hypothesis_illustration() are preserved.

If there is no behavior x outcome data yet, this engine runs successfully but
returns zero hypotheses. It does not fabricate placeholder hypotheses to look
complete.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import uuid
import pandas as pd

HYPOTHESIS_STATUSES = {
    "PROPOSED", "ELIGIBLE_FOR_TESTING", "TESTED", "SUPPORTED", "NOT_SUPPORTED",
    "INCONCLUSIVE", "HELD_OUT_PENDING", "REPLICATED", "FAILED_REPLICATION",
}

# MVP CONFIGURATION -- NOT SCIENTIFICALLY VALIDATED THRESHOLDS.
# Matches the values already used in hypothesis_readiness.py's READINESS_CONFIG
# for consistency; not a new, separately-invented number.
ELIGIBILITY_CONFIG = {
    "_label": "MVP CONFIGURATION -- NOT SCIENTIFICALLY VALIDATED THRESHOLDS",
    "minimum_sample_size": 5,
    "minimum_unique_applications": 3,
}


@dataclass
class Hypothesis:
    hypothesis_id: str
    mechanism_id: str
    scenario_id: str
    journey_stage: str
    population: str
    segment: str
    outcome_variable: str
    null_hypothesis: str
    alternative_hypothesis: str
    comparison_group: str
    sample_size: int
    discovery_dataset_reference: str
    status: str
    created_date: str
    tested_date: str
    validation_status: str
    # kept from the prior schema -- useful analyst-facing context, not required
    # by the new spec but not removed since nothing asked us to drop it
    mechanism_name: str = ""
    hypothesis_statement: str = ""
    proposed_statistical_test: str = ""
    analyst_notes: str = ""

    def as_dict(self):
        return asdict(self)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _choose_proposed_test(n_group_a: int, n_group_b: int) -> str:
    """Transparent heuristic for suggesting a starting test -- the analyst can
    always override. Not itself a statistical decision."""
    if min(n_group_a, n_group_b) < 30:
        return "Fisher's exact test (small expected cell counts)"
    return "Chi-square test of independence"


def _dominant_journey_stage(mech_id: str, scenario_library: pd.DataFrame) -> str:
    if scenario_library is None or len(scenario_library) == 0:
        return "unknown"
    sub = scenario_library[scenario_library.mechanism_id == mech_id]
    if len(sub) == 0:
        return "unknown"
    return sub.journey_stage.mode().iloc[0]


def generate_hypotheses(behavior_outcome_df: pd.DataFrame,
                         scenario_library: pd.DataFrame = None,
                         outcome_variable: str = "final_disposition",
                         config: dict = None) -> pd.DataFrame:
    """
    behavior_outcome_df: output of behavior_outcome_builder.build_behavior_outcome_dataset()
        -- already restricted to discovery + hypothesis_generation splits.
    scenario_library: optional output of scenario_mapping.build_scenario_library(),
        used only to attach a representative scenario_id/journey_stage per mechanism.
    """
    cfg = config or ELIGIBILITY_CONFIG
    cols = list(Hypothesis.__annotations__.keys())

    if behavior_outcome_df is None or len(behavior_outcome_df) == 0:
        return pd.DataFrame(columns=cols)

    scenario_by_mech = {}
    if scenario_library is not None and len(scenario_library) > 0:
        for mech_id, sub in scenario_library.groupby("mechanism_id"):
            scenario_by_mech[mech_id] = sub.scenario_id.iloc[0]

    rows = []
    for mech_id, sub in behavior_outcome_df.groupby("mechanism_id"):
        mech_name = sub.mechanism_name.iloc[0] if "mechanism_name" in sub.columns else ""
        sample_size = len(sub)
        n_unique_apps = sub.application_id.nunique()
        journey_stage = _dominant_journey_stage(mech_id, scenario_library)
        scenario_id = scenario_by_mech.get(mech_id, "")

        statement = (
            f"Among candidates reaching accepted-offer stage, applications containing "
            f"approved evidence consistent with '{mech_name}' will show a different "
            f"post-acceptance joining outcome distribution than applications without "
            f"that approved evidence."
        )

        eligible = sample_size >= cfg["minimum_sample_size"] and n_unique_apps >= cfg["minimum_unique_applications"]

        rows.append(Hypothesis(
            hypothesis_id=f"HYP-{uuid.uuid4().hex[:12]}",
            mechanism_id=mech_id,
            scenario_id=scenario_id,
            journey_stage=journey_stage,
            population="Candidates who reached accepted-offer stage, discovery + hypothesis_generation splits only",
            segment="All job families (not yet stratified -- see analyst_notes)",
            outcome_variable=outcome_variable,
            null_hypothesis=f"There is no difference in {outcome_variable} distribution between "
                             f"applications with vs. without approved evidence for '{mech_name}'.",
            alternative_hypothesis=f"There is a difference in {outcome_variable} distribution between "
                                    f"applications with vs. without approved evidence for '{mech_name}'.",
            comparison_group=f"Applications with mechanism_id={mech_id} vs. applications without it, "
                              f"within the same population",
            sample_size=int(sample_size),
            discovery_dataset_reference="behavior_outcome_dataset (discovery + hypothesis_generation splits)",
            status="ELIGIBLE_FOR_TESTING" if eligible else "PROPOSED",
            created_date=_now_iso(),
            tested_date="",
            validation_status="",
            mechanism_name=mech_name,
            hypothesis_statement=statement,
            proposed_statistical_test=_choose_proposed_test(n_unique_apps, n_unique_apps),
            analyst_notes="Auto-generated from approved evidence -> approved mechanism mappings -> "
                           "behavior_outcome_dataset. Not stratified by segment in this MVP pass. "
                           f"Eligibility thresholds: {cfg['_label']}.",
        ).as_dict())

    return pd.DataFrame(rows, columns=cols)


def demo_hypothesis_illustration() -> dict:
    """
    ILLUSTRATIVE example only -- never written to any output file or database
    table. Shows the current output shape.
    """
    return Hypothesis(
        hypothesis_id="HYP-DEMO-EXAMPLE",
        mechanism_id="BM-EXAMPLE",
        scenario_id="SCN-EXAMPLE",
        journey_stage="offer_accepted",
        population="Candidates who reached accepted-offer stage, discovery + hypothesis_generation splits only",
        segment="All job families (not yet stratified)",
        outcome_variable="final_disposition",
        null_hypothesis="There is no difference in outcome distribution between the two groups.",
        alternative_hypothesis="There is a difference in outcome distribution between the two groups.",
        comparison_group="Applications with the example mechanism vs. applications without it",
        sample_size=0,
        discovery_dataset_reference="behavior_outcome_dataset (discovery + hypothesis_generation splits)",
        status="ILLUSTRATIVE ONLY -- not a real generated hypothesis",
        created_date=_now_iso(),
        tested_date="",
        validation_status="",
        mechanism_name="[illustrative placeholder -- not a real mechanism]",
        hypothesis_statement=(
            "Among candidates reaching accepted-offer stage, applications containing approved "
            "evidence consistent with [mechanism] will show a different post-acceptance joining "
            "outcome distribution than applications without that approved evidence."
        ),
        proposed_statistical_test="Chi-square test of independence (or Fisher's exact if group sizes are small)",
        analyst_notes="This record exists only to demonstrate output shape. It is never written to "
                      "bj_hypotheses or any CSV output.",
    ).as_dict()
