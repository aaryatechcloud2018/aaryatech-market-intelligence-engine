"""
run_hypothesis_tests.py -- FINAL DEMONSTRATION RUN ONLY.

Runs the existing statistical_engine functions against every
ELIGIBLE_FOR_TESTING hypothesis. Uses ONLY discovery + hypothesis_generation
splits. Outcome operationalized as binary joined vs not-joined -- stated
explicitly in each result's limitations field.
"""
from datetime import datetime, timezone
import subprocess
import pandas as pd

from .statistical_engine import (
    chi_square_test, fishers_exact_test, grade_evidence, StatisticalResult,
    benjamini_hochberg_adjustment,
)

ALLOWED_SPLITS = {"discovery", "hypothesis_generation"}


def _code_version_reference() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
    except Exception:
        return "unknown"


def run_eligible_hypothesis_tests(hypotheses_df, bridge_df, applications_df):
    pop = applications_df[
        (applications_df.offer_accepted == True) & (applications_df.research_split.isin(ALLOWED_SPLITS))
    ].copy()
    pop["joined"] = pop.final_disposition.isin(["joined_on_time", "joined_late"])

    code_ref = _code_version_reference()
    run_date = datetime.now(timezone.utc).isoformat()

    results = []
    hyps = hypotheses_df.copy()

    for idx, h in hyps.iterrows():
        if h.status != "ELIGIBLE_FOR_TESTING":
            continue
        mech_id = h.mechanism_id
        with_mech = set(bridge_df[bridge_df.mechanism_id == mech_id].application_id)
        pop["has_mechanism"] = pop.application_id.isin(with_mech)

        table = pd.crosstab(pop.has_mechanism, pop.joined)
        table = table.reindex(index=[False, True], columns=[False, True], fill_value=0)
        n = int(table.to_numpy().sum())
        group_with = int(table.loc[True].sum())
        group_without = int(table.loc[False].sum())
        expected_min_cell = table.to_numpy().min() if table.to_numpy().size else 0
        use_fisher = group_with < 30 or group_without < 30 or expected_min_cell < 5

        if use_fisher:
            r = fishers_exact_test(table)
            test_name = "fishers_exact_test"
        else:
            r = chi_square_test(table)
            test_name = "chi_square_test"

        rate_with = table.loc[True, True] / group_with if group_with else float("nan")
        rate_without = table.loc[False, True] / group_without if group_without else float("nan")
        if rate_with == rate_with and rate_without == rate_without:
            direction = "higher_joining_with_mechanism" if rate_with > rate_without else \
                        ("lower_joining_with_mechanism" if rate_with < rate_without else "no_difference")
        else:
            direction = "indeterminate"

        grade = grade_evidence(r["p_value"], r["effect_size"], r["effect_size_metric"])

        result = StatisticalResult(
            hypothesis_id=h.hypothesis_id, test_name=test_name, sample_size=n,
            group_sizes=f"with_mechanism={group_with};without_mechanism={group_without}",
            effect_size=float(r["effect_size"]) if r["effect_size"] == r["effect_size"] else float("nan"),
            effect_size_metric=r["effect_size_metric"],
            confidence_interval="not computed for this test" if test_name == "chi_square_test" else "see odds ratio",
            test_statistic=float(r["test_statistic"]) if r["test_statistic"] == r["test_statistic"] else float("nan"),
            p_value=float(r["p_value"]),
            adjusted_p_value=float("nan"),
            multiple_testing_adjustment="Benjamini-Hochberg (applied across all tested hypotheses in this run)",
            covariates_controlled="none (unadjusted 2x2 comparison)",
            result_direction=direction,
            evidence_grade=grade,
            validation_dataset="discovery+hypothesis_generation",
            run_date=run_date,
            code_version_reference=code_ref,
            limitations="Outcome operationalized as binary joined-vs-not-joined (simplified from the "
                        "6-category final_disposition). Association only -- not a causal claim. "
                        "held_out_test was not used.",
        )
        results.append(result.as_dict())

        hyps.at[idx, "status"] = "TESTED"
        hyps.at[idx, "tested_date"] = run_date
        hyps.at[idx, "validation_status"] = "TESTED_NOT_HELD_OUT_VALIDATED"

    results_df = pd.DataFrame(results, columns=list(StatisticalResult.__annotations__.keys()))

    if len(results_df):
        results_df["adjusted_p_value"] = benjamini_hochberg_adjustment(results_df.p_value.tolist())
        results_df["evidence_grade"] = [
            grade_evidence(row.adjusted_p_value, row.effect_size, row.effect_size_metric)
            for _, row in results_df.iterrows()
        ]

    return hyps, results_df
