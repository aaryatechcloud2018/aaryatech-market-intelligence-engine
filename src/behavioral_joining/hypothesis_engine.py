"""
hypothesis_engine.py

Generates falsifiable behavioral hypothesis RECORDS from human-approved evidence +
human-approved mechanism mappings ONLY.

If no approved mechanism mappings exist yet (which is the current state, since the
mechanism library itself hasn't been supplied -- see mechanism_library.py), this
engine runs successfully but returns zero hypotheses with status
'waiting_for_mechanism_mappings'. It does not fabricate placeholder hypotheses to
look complete.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import uuid
import pandas as pd

HYPOTHESIS_STATUSES = {"draft", "waiting_for_mechanism_mappings", "ready_for_testing", "retired"}


@dataclass
class Hypothesis:
    hypothesis_id: str
    mechanism_id: str
    mechanism_name: str
    population: str
    comparison_group: str
    outcome_variable: str
    hypothesis_statement: str
    null_hypothesis: str
    alternative_hypothesis: str
    supporting_evidence_count: int
    candidate_covariates: str
    proposed_statistical_test: str
    status: str
    analyst_notes: str = ""

    def as_dict(self):
        return asdict(self)


def _choose_proposed_test(n_group_a: int, n_group_b: int) -> str:
    """Simple, transparent heuristic for suggesting a starting test -- the analyst
    can always override via analyst_notes. Not a statistical decision by itself."""
    if min(n_group_a, n_group_b) < 30:
        return "Fisher's exact test (small expected cell counts)"
    return "Chi-square test of independence"


def generate_hypotheses(approved_evidence: pd.DataFrame,
                         approved_mechanism_mappings: pd.DataFrame,
                         outcome_variable: str = "final_disposition") -> pd.DataFrame:
    """
    approved_evidence: evidence_review rows with review_decision in [approved, edited]
    approved_mechanism_mappings: mechanism_mapping_review rows with review_decision in
        [approved, edited], each carrying a real (non-empty) mechanism_id.
    """
    if approved_mechanism_mappings is None or len(approved_mechanism_mappings) == 0:
        return pd.DataFrame(columns=list(Hypothesis.__annotations__.keys()))

    real_mappings = approved_mechanism_mappings[
        approved_mechanism_mappings.get("edited_mechanism_id", "").astype(str).str.len().gt(0) |
        approved_mechanism_mappings.get("original_mechanism_id", "").astype(str).str.len().gt(0)
    ].copy()
    if len(real_mappings) == 0:
        return pd.DataFrame(columns=list(Hypothesis.__annotations__.keys()))

    real_mappings["effective_mechanism_id"] = real_mappings["edited_mechanism_id"].where(
        real_mappings["edited_mechanism_id"].astype(str).str.len().gt(0),
        real_mappings["original_mechanism_id"],
    )
    real_mappings["effective_mechanism_name"] = real_mappings["edited_mechanism_name"].where(
        real_mappings["edited_mechanism_name"].astype(str).str.len().gt(0),
        real_mappings["original_mechanism_name"],
    )

    rows = []
    for (mech_id, mech_name), sub in real_mappings.groupby(["effective_mechanism_id", "effective_mechanism_name"]):
        n_with_evidence = sub.application_id.nunique()
        statement = (
            f"Among candidates reaching accepted-offer stage, applications containing "
            f"approved evidence consistent with '{mech_name}' will show a different "
            f"post-acceptance joining outcome distribution than applications without "
            f"that approved evidence."
        )
        rows.append(Hypothesis(
            hypothesis_id=f"HYP-{uuid.uuid4().hex[:12]}",
            mechanism_id=mech_id,
            mechanism_name=mech_name,
            population="Candidates who reached accepted-offer stage (offer_accepted = True)",
            comparison_group=f"Applications with vs. without approved evidence mapped to '{mech_name}'",
            outcome_variable=outcome_variable,
            hypothesis_statement=statement,
            null_hypothesis=f"There is no difference in {outcome_variable} distribution between "
                             f"applications with vs. without approved evidence for '{mech_name}'.",
            alternative_hypothesis=f"There is a difference in {outcome_variable} distribution between "
                                    f"applications with vs. without approved evidence for '{mech_name}'.",
            supporting_evidence_count=int(n_with_evidence),
            candidate_covariates="job_family, client_account_id, recruiter_id, pay_change_percentage, "
                                  "notice_period_days, work_arrangement",
            proposed_statistical_test=_choose_proposed_test(n_with_evidence, n_with_evidence),
            status="ready_for_testing" if n_with_evidence >= 10 else "draft",
            analyst_notes="Auto-generated from approved mechanism mappings. Test not yet run "
                           "(discovery/hypothesis_generation splits only; held_out_test protected).",
        ).as_dict())

    return pd.DataFrame(rows, columns=list(Hypothesis.__annotations__.keys()))


def demo_hypothesis_illustration() -> dict:
    """
    Returns a single ILLUSTRATIVE example (not a real hypothesis, not written to any
    output file or database table) showing the shape of what this engine produces
    once real approved mechanism mappings exist. Used only in documentation/reports.
    """
    return Hypothesis(
        hypothesis_id="HYP-DEMO-EXAMPLE",
        mechanism_id="MECH-EXAMPLE",
        mechanism_name="[illustrative placeholder -- not a real mechanism]",
        population="Candidates who reached accepted-offer stage (offer_accepted = True)",
        comparison_group="Applications with vs. without approved evidence mapped to the example mechanism",
        outcome_variable="final_disposition",
        hypothesis_statement=(
            "Among candidates reaching accepted-offer stage, applications containing approved "
            "evidence consistent with [mechanism] will show a different post-acceptance joining "
            "outcome distribution than applications without that approved evidence."
        ),
        null_hypothesis="There is no difference in outcome distribution between the two groups.",
        alternative_hypothesis="There is a difference in outcome distribution between the two groups.",
        supporting_evidence_count=0,
        candidate_covariates="job_family, client_account_id, recruiter_id, pay_change_percentage",
        proposed_statistical_test="Chi-square test of independence (or Fisher's exact if group sizes are small)",
        status="ILLUSTRATIVE ONLY -- not a real generated hypothesis",
        analyst_notes="This record exists only to demonstrate output shape. It is never written to "
                      "bj_hypotheses or any CSV output.",
    ).as_dict()
