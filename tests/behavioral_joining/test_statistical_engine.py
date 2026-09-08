import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.behavioral_joining.statistical_engine import (
    chi_square_test, fishers_exact_test, t_test, mann_whitney_u, compare_proportions,
    proportion_confidence_interval, logistic_regression_confounder_check,
    benjamini_hochberg_adjustment, grade_evidence, choose_test,
    run_held_out_validation, HeldOutTestNotAuthorizedError, EVIDENCE_GRADES,
)


def test_chi_square_test_runs():
    table = pd.DataFrame([[50, 150], [70, 130]])
    result = chi_square_test(table)
    assert "p_value" in result and "effect_size" in result
    assert 0 <= result["p_value"] <= 1


def test_fishers_exact_test_runs():
    table = pd.DataFrame([[8, 2], [3, 7]])
    result = fishers_exact_test(table)
    assert 0 <= result["p_value"] <= 1


def test_t_test_runs():
    a = pd.Series(np.random.RandomState(1).normal(10, 2, 50))
    b = pd.Series(np.random.RandomState(2).normal(12, 2, 50))
    result = t_test(a, b)
    assert "effect_size" in result and result["effect_size_metric"] == "Cohen's d"


def test_mann_whitney_u_runs():
    a = pd.Series(np.random.RandomState(1).exponential(2, 40))
    b = pd.Series(np.random.RandomState(2).exponential(3, 40))
    result = mann_whitney_u(a, b)
    assert 0 <= result["p_value"] <= 1


def test_compare_proportions_small_sample_uses_fisher():
    result = compare_proportions(3, 10, 7, 10)
    assert "proportion_a" in result and "proportion_b" in result


def test_proportion_confidence_interval_bounds():
    lo, hi = proportion_confidence_interval(50, 100)
    assert 0 <= lo <= 0.5 <= hi <= 1


def test_logistic_regression_confounder_check_runs():
    rng = np.random.RandomState(0)
    n = 200
    df = pd.DataFrame({
        "outcome": rng.binomial(1, 0.5, n),
        "predictor": rng.choice(["A", "B"], n),
        "covariate1": rng.choice(["X", "Y", "Z"], n),
    })
    result = logistic_regression_confounder_check(df, "outcome", "predictor", ["covariate1"])
    assert result["status"] == "fit"
    assert "odds_ratios" in result


def test_logistic_regression_insufficient_data():
    df = pd.DataFrame({"outcome": [1, 0, 1], "predictor": ["A", "B", "A"], "cov": ["X", "Y", "X"]})
    result = logistic_regression_confounder_check(df, "outcome", "predictor", ["cov"])
    assert result["status"] == "insufficient_data"


def test_benjamini_hochberg_adjustment():
    p_values = [0.001, 0.02, 0.04, 0.5]
    adjusted = benjamini_hochberg_adjustment(p_values)
    assert len(adjusted) == 4
    assert all(0 <= p <= 1 for p in adjusted)
    assert all(a >= b for a, b in zip(adjusted, p_values))  # adjustment never decreases p


def test_grade_evidence_significant_and_meaningful():
    assert grade_evidence(0.01, 0.3, "Cramer's V") == "SUPPORTED"


def test_grade_evidence_significant_but_tiny_effect_is_weak():
    assert grade_evidence(0.01, 0.02, "Cramer's V") == "WEAK"


def test_grade_evidence_not_significant_is_inconclusive():
    assert grade_evidence(0.4, 0.3, "Cramer's V") == "INCONCLUSIVE"


def test_grade_evidence_p_value_alone_never_equals_supported():
    """p < 0.05 must not automatically mean SUPPORTED without checking effect size."""
    assert grade_evidence(0.001, 0.01, "Cramer's V") != "SUPPORTED"


def test_evidence_grades_are_the_required_set():
    assert EVIDENCE_GRADES == {"SUPPORTED", "WEAK", "CONTRADICTED", "INCONCLUSIVE"}


def test_choose_test_categorical_pair():
    assert choose_test("categorical", "categorical", expected_min_cell_count=3) == "fishers_exact_test"
    assert choose_test("categorical", "categorical", expected_min_cell_count=50) == "chi_square_test"


# --- held-out safeguard (also covered in test_research_split_safeguards.py) ---

def test_held_out_validation_cannot_run_without_authorization():
    with pytest.raises(HeldOutTestNotAuthorizedError):
        run_held_out_validation()


def test_no_default_authorization_token_exists():
    import inspect
    sig = inspect.signature(run_held_out_validation)
    assert sig.parameters["authorized"].default is False
    assert sig.parameters["authorization_token"].default is None
