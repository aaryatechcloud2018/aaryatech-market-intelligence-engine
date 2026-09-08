"""
statistical_engine.py

Reusable statistical testing MODULE (Part K). Every function here is safe to call
against discovery/hypothesis_generation data at any time. The one function that can
touch held_out_test data (run_held_out_validation) is hard-gated behind an explicit
authorization argument specifically so it cannot be triggered by accident -- there is
no code path anywhere else in this project (including run_behavioral_pipeline.py)
that calls it.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import math
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression

EVIDENCE_GRADES = {"SUPPORTED", "WEAK", "CONTRADICTED", "INCONCLUSIVE"}


@dataclass
class StatisticalResult:
    hypothesis_id: str
    test_name: str
    sample_size: int
    group_sizes: str                 # e.g. "with_evidence=120;without_evidence=380"
    effect_size: float
    effect_size_metric: str
    confidence_interval: str         # "[low, high]" as a string for CSV/DB storage
    test_statistic: float
    p_value: float
    multiple_testing_adjustment: str
    covariates_controlled: str
    result_direction: str
    evidence_grade: str
    limitations: str

    def as_dict(self):
        return asdict(self)


# ---------------------------------------------------------------------------
# Test selection helper
# ---------------------------------------------------------------------------
def choose_test(outcome_type: str, group_type: str, expected_min_cell_count: int = None) -> str:
    """outcome_type / group_type: 'categorical' or 'continuous'. Returns a recommended
    test name. This is a starting suggestion for the analyst, not an automatic decision."""
    if outcome_type == "categorical" and group_type == "categorical":
        if expected_min_cell_count is not None and expected_min_cell_count < 5:
            return "fishers_exact_test"
        return "chi_square_test"
    if outcome_type == "continuous" and group_type == "categorical":
        return "t_test (if approximately normal) or mann_whitney_u (if not)"
    if outcome_type == "categorical" and group_type == "continuous":
        return "logistic_regression"
    return "consult analyst -- no default mapping for this combination"


# ---------------------------------------------------------------------------
# Core test functions
# ---------------------------------------------------------------------------
def chi_square_test(contingency_table: pd.DataFrame):
    stat, p, dof, expected = stats.chi2_contingency(contingency_table)
    n = contingency_table.to_numpy().sum()
    min_dim = min(contingency_table.shape) - 1
    cramers_v = math.sqrt((stat / n) / min_dim) if min_dim > 0 and n > 0 else float("nan")
    return {"test_statistic": stat, "p_value": p, "dof": dof, "effect_size": cramers_v,
            "effect_size_metric": "Cramer's V", "expected_counts": expected}


def fishers_exact_test(table_2x2: pd.DataFrame):
    odds_ratio, p = stats.fisher_exact(table_2x2.to_numpy())
    return {"test_statistic": odds_ratio, "p_value": p, "effect_size": odds_ratio,
            "effect_size_metric": "odds ratio"}


def t_test(group_a: pd.Series, group_b: pd.Series, equal_var: bool = False):
    stat, p = stats.ttest_ind(group_a.dropna(), group_b.dropna(), equal_var=equal_var)
    pooled_sd = math.sqrt((group_a.var(ddof=1) + group_b.var(ddof=1)) / 2)
    cohens_d = (group_a.mean() - group_b.mean()) / pooled_sd if pooled_sd else float("nan")
    return {"test_statistic": stat, "p_value": p, "effect_size": cohens_d, "effect_size_metric": "Cohen's d"}


def mann_whitney_u(group_a: pd.Series, group_b: pd.Series):
    stat, p = stats.mannwhitneyu(group_a.dropna(), group_b.dropna(), alternative="two-sided")
    n1, n2 = len(group_a.dropna()), len(group_b.dropna())
    rank_biserial = 1 - (2 * stat) / (n1 * n2) if n1 and n2 else float("nan")
    return {"test_statistic": stat, "p_value": p, "effect_size": rank_biserial,
            "effect_size_metric": "rank-biserial correlation"}


def proportion_confidence_interval(successes: int, n: int, confidence: float = 0.95):
    if n == 0:
        return (float("nan"), float("nan"))
    p_hat = successes / n
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    se = math.sqrt(p_hat * (1 - p_hat) / n)
    return (max(0.0, p_hat - z * se), min(1.0, p_hat + z * se))


def compare_proportions(successes_a: int, n_a: int, successes_b: int, n_b: int):
    table = pd.DataFrame([[successes_a, n_a - successes_a], [successes_b, n_b - successes_b]])
    if n_a < 30 or n_b < 30 or (table.to_numpy() < 5).any():
        result = fishers_exact_test(table)
    else:
        result = chi_square_test(table)
    ci_a = proportion_confidence_interval(successes_a, n_a)
    ci_b = proportion_confidence_interval(successes_b, n_b)
    result["proportion_a"] = successes_a / n_a if n_a else float("nan")
    result["proportion_b"] = successes_b / n_b if n_b else float("nan")
    result["ci_a"] = ci_a
    result["ci_b"] = ci_b
    return result


def logistic_regression_confounder_check(df: pd.DataFrame, outcome_col: str,
                                          predictor_col: str, covariate_cols: list[str]):
    """For explanatory/confounder analysis where scientifically justified -- e.g.
    checking whether an apparent evidence/outcome relationship survives controlling
    for job_family, client, recruiter, pay change, etc. Returns coefficients and
    odds ratios; does NOT produce a joining-probability prediction for any individual."""
    work = df[[outcome_col, predictor_col] + covariate_cols].dropna().copy()
    X = pd.get_dummies(work[[predictor_col] + covariate_cols], drop_first=True)
    y = work[outcome_col].astype(int)
    if y.nunique() < 2 or len(work) < 20:
        return {"status": "insufficient_data", "n": len(work)}
    model = LogisticRegression(max_iter=1000)
    model.fit(X, y)
    coefs = dict(zip(X.columns, model.coef_[0]))
    odds_ratios = {k: float(np.exp(v)) for k, v in coefs.items()}
    return {"status": "fit", "n": len(work), "coefficients": coefs, "odds_ratios": odds_ratios,
            "predictor_column_used": predictor_col, "covariates_used": covariate_cols}


def benjamini_hochberg_adjustment(p_values: list[float]) -> list[float]:
    """Standard multiple-testing correction, for use once more than one hypothesis
    is tested in the same analysis pass."""
    p = np.array(p_values)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order]
    adjusted = ranked * n / (np.arange(n) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    adjusted = np.clip(adjusted, 0, 1)
    out = np.empty(n)
    out[order] = adjusted
    return out.tolist()


def grade_evidence(p_value: float, effect_size: float, effect_size_metric: str,
                    alpha: float = 0.05, small_effect_threshold: float = 0.1) -> str:
    """p < 0.05 is NOT automatically treated as important -- effect size and direction
    both matter. This is a starting classification for analyst review, not a final verdict."""
    if p_value is None or (isinstance(p_value, float) and math.isnan(p_value)):
        return "INCONCLUSIVE"
    if p_value >= alpha:
        return "INCONCLUSIVE"
    if effect_size is None or (isinstance(effect_size, float) and math.isnan(effect_size)):
        return "WEAK"
    if abs(effect_size) < small_effect_threshold:
        return "WEAK"
    return "SUPPORTED"


# ---------------------------------------------------------------------------
# HARD SAFEGUARD: held_out_test protection
# ---------------------------------------------------------------------------
class HeldOutTestNotAuthorizedError(RuntimeError):
    pass


def run_held_out_validation(*args, authorized: bool = False, authorization_token: str = None, **kwargs):
    """
    Placeholder for the eventual formal held-out validation run.

    This function CANNOT run without both authorized=True AND a non-empty
    authorization_token supplied explicitly by the caller at call time. There is no
    default, no environment variable, and no config file that can satisfy this --
    it must be passed directly, deliberately, by a human, in a future explicit
    approval step. No code elsewhere in this project (including the orchestrator)
    ever calls this function.
    """
    if not authorized or not authorization_token:
        raise HeldOutTestNotAuthorizedError(
            "held_out_test validation is protected and was NOT run. This function requires "
            "explicit authorized=True and a non-empty authorization_token passed directly by "
            "a human analyst as part of a deliberate future approval step. This is not "
            "something the pipeline, a config file, or an environment variable can trigger."
        )
    raise NotImplementedError(
        "Held-out validation logic is intentionally not implemented yet. Building it now, "
        "before discovery/hypothesis-generation work is even reviewed, would create pressure "
        "to use it prematurely. It will be implemented as part of the explicit final "
        "validation step you approve separately."
    )
