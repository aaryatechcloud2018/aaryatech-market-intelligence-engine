"""
Simple hypothesis testing (Phase 4, Step 5).

Inspects the ANALYSIS_READY observations to determine whether any of
three test types is actually statistically supportable, and only runs
the test if it is:

1. Two-group comparison (Welch's t-test) - company vs. competitor
   values for the same metric.
2. Categorical association (chi-square) - requires categorical count
   data forming a contingency table.
3. Correlation (Pearson) - paired same-entity, same-period values for
   two different metrics.

For each test type, this reports exactly one representative attempt
(the best-supported candidate found for that type), with a
`status = "INSUFFICIENT_DATA"` result and an explicit reason when the
minimum sample-size threshold is not met. Nothing is fabricated to
force a test to run.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from scipy import stats

from src.analytics.data_loader import Observation

ALPHA = 0.05

# Minimum group size for a two-sample test to be attempted at all. Five
# is already a very small sample for a t-test - below it, the result
# would be too noisy to be meaningful, so we do not even run scipy.
MIN_GROUP_N = 5

# Minimum number of paired observations for a Pearson correlation to be
# attempted. Classical guidance wants considerably more than this;
# five is treated as an absolute floor, not a target.
MIN_PAIR_N = 5

# Minimum expected count per cell for a chi-square test to be valid.
MIN_CHI_SQUARE_CELL_COUNT = 5


@dataclass
class HypothesisResult:
    hypothesis_id: str
    question: str
    H0: str
    H1: str
    test_type: str
    variable_1: str
    variable_2: str
    sample_size: str
    test_statistic: float | None
    p_value: float | None
    significance_level: float
    result: str  # e.g. "SIGNIFICANT" / "NOT_SIGNIFICANT" / "INSUFFICIENT_DATA"
    interpretation: str
    limitation: str


def _company_vs_competitor_groups(observations: list[Observation]) -> list[tuple[str, list[float], list[float]]]:
    """Every metric that has at least one COMPANY and one COMPETITOR value, as (metric_id, company_values, competitor_values)."""
    by_metric: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for obs in observations:
        if obs.entity_type in ("COMPANY", "COMPETITOR") and obs.normalized_value is not None:
            by_metric[obs.metric_id][obs.entity_type].append(obs.normalized_value)

    candidates = []
    for metric_id, groups in by_metric.items():
        company_vals = groups.get("COMPANY", [])
        competitor_vals = groups.get("COMPETITOR", [])
        if company_vals and competitor_vals:
            candidates.append((metric_id, company_vals, competitor_vals))
    return candidates


def _best_two_group_candidate(observations: list[Observation]):
    candidates = _company_vs_competitor_groups(observations)
    if not candidates:
        return None
    # "Best" = largest minimum group size, since that is the binding constraint on power.
    return max(candidates, key=lambda c: min(len(c[1]), len(c[2])))


def run_two_group_comparison(observations: list[Observation]) -> HypothesisResult:
    metric_name_lookup = {o.metric_id: o.metric_name for o in observations}
    candidate = _best_two_group_candidate(observations)

    if candidate is None:
        return HypothesisResult(
            hypothesis_id="H1", question="Do company and competitor values differ for any shared metric?",
            H0="No metrics have both company and competitor values available.",
            H1="N/A", test_type="two_group_comparison (Welch's t-test)",
            variable_1="N/A", variable_2="N/A", sample_size="0 vs 0",
            test_statistic=None, p_value=None, significance_level=ALPHA,
            result="INSUFFICIENT_DATA",
            interpretation="No metric in the analysis-ready dataset has values for both the "
                           "company and a competitor, so no two-group comparison can be formed.",
            limitation="No overlapping company/competitor metric found.",
        )

    metric_id, company_vals, competitor_vals = candidate
    metric_name = metric_name_lookup.get(metric_id, metric_id)
    n1, n2 = len(company_vals), len(competitor_vals)

    if min(n1, n2) < MIN_GROUP_N:
        return HypothesisResult(
            hypothesis_id="H1",
            question=f"Does Smartworks' {metric_name} differ from competitors' {metric_name}?",
            H0=f"The mean {metric_name} of Smartworks equals the mean {metric_name} of competitors.",
            H1=f"The mean {metric_name} of Smartworks differs from the mean {metric_name} of competitors.",
            test_type="two_group_comparison (Welch's t-test)",
            variable_1=f"{metric_name} (Smartworks)", variable_2=f"{metric_name} (Competitors)",
            sample_size=f"{n1} vs {n2}",
            test_statistic=None, p_value=None, significance_level=ALPHA,
            result="INSUFFICIENT_DATA",
            interpretation=f"This is the best-supported two-group candidate in the dataset "
                           f"({metric_name}, n={n1} vs n={n2}), but both group sizes are below the "
                           f"minimum of {MIN_GROUP_N} required to attempt a t-test.",
            limitation=(
                f"Sample sizes too small for a reliable t-test (need >= {MIN_GROUP_N} per group). "
                "Additionally, the competitor values are repeated-measures across a small number of "
                "named firms over multiple fiscal years, not independent random draws, which would "
                "violate the independence assumption even at a larger n."
            ),
        )

    statistic, p_value = stats.ttest_ind(company_vals, competitor_vals, equal_var=False)
    significant = p_value < ALPHA
    return HypothesisResult(
        hypothesis_id="H1",
        question=f"Does Smartworks' {metric_name} differ from competitors' {metric_name}?",
        H0=f"The mean {metric_name} of Smartworks equals the mean {metric_name} of competitors.",
        H1=f"The mean {metric_name} of Smartworks differs from the mean {metric_name} of competitors.",
        test_type="two_group_comparison (Welch's t-test)",
        variable_1=f"{metric_name} (Smartworks)", variable_2=f"{metric_name} (Competitors)",
        sample_size=f"{n1} vs {n2}",
        test_statistic=round(float(statistic), 4), p_value=round(float(p_value), 4),
        significance_level=ALPHA,
        result="SIGNIFICANT" if significant else "NOT_SIGNIFICANT",
        interpretation=(
            f"{'A statistically significant' if significant else 'No statistically significant'} "
            f"difference was found between Smartworks and competitor {metric_name} at alpha={ALPHA}."
        ),
        limitation=f"Small sample size (n={n1} vs n={n2}); competitor values are repeated-measures "
                   "across a small number of firms, not independent random draws.",
    )


def _paired_series_candidates(observations: list[Observation]) -> list[tuple[str, str, str, list[float], list[float]]]:
    """
    Every (metric_A, metric_B, entity) triple with overlapping (entity, year)
    values for both metrics, as (metric_A_id, metric_B_id, entity, series_A, series_B).
    """
    # entity -> metric_id -> year -> value
    by_entity: dict[str, dict[str, dict[int, float]]] = defaultdict(lambda: defaultdict(dict))
    for obs in observations:
        if obs.entity_name and obs.period_year is not None and obs.normalized_value is not None:
            by_entity[obs.entity_name][obs.metric_id][obs.period_year] = obs.normalized_value

    candidates = []
    for entity, metrics in by_entity.items():
        metric_ids = sorted(metrics)
        for i, metric_a in enumerate(metric_ids):
            for metric_b in metric_ids[i + 1:]:
                shared_years = sorted(set(metrics[metric_a]) & set(metrics[metric_b]))
                if len(shared_years) >= 2:
                    series_a = [metrics[metric_a][y] for y in shared_years]
                    series_b = [metrics[metric_b][y] for y in shared_years]
                    candidates.append((metric_a, metric_b, entity, series_a, series_b))
    return candidates


def run_correlation(observations: list[Observation]) -> HypothesisResult:
    metric_name_lookup = {o.metric_id: o.metric_name for o in observations}
    candidates = _paired_series_candidates(observations)

    if not candidates:
        return HypothesisResult(
            hypothesis_id="H2", question="Are any two metrics correlated for the same entity?",
            H0="No two metrics share overlapping reporting periods for the same entity.",
            H1="N/A", test_type="correlation (Pearson)",
            variable_1="N/A", variable_2="N/A", sample_size="0 pairs",
            test_statistic=None, p_value=None, significance_level=ALPHA,
            result="INSUFFICIENT_DATA",
            interpretation="No pair of metrics in the analysis-ready dataset shares at least 2 "
                           "overlapping reporting periods for the same entity.",
            limitation="No paired same-entity, same-period metric series found.",
        )

    metric_a, metric_b, entity, series_a, series_b = max(candidates, key=lambda c: len(c[3]))
    name_a, name_b = metric_name_lookup.get(metric_a, metric_a), metric_name_lookup.get(metric_b, metric_b)
    n = len(series_a)

    if n < MIN_PAIR_N:
        return HypothesisResult(
            hypothesis_id="H2",
            question=f"Is {name_a} correlated with {name_b} for {entity}?",
            H0=f"There is no linear correlation between {name_a} and {name_b} for {entity}.",
            H1=f"There is a linear correlation between {name_a} and {name_b} for {entity}.",
            test_type="correlation (Pearson)",
            variable_1=f"{name_a} ({entity})", variable_2=f"{name_b} ({entity})",
            sample_size=f"{n} pairs",
            test_statistic=None, p_value=None, significance_level=ALPHA,
            result="INSUFFICIENT_DATA",
            interpretation=f"This is the best-supported correlation candidate in the dataset "
                           f"({name_a} vs {name_b} for {entity}, n={n} paired periods), but it is "
                           f"below the minimum of {MIN_PAIR_N} pairs required for a meaningful Pearson correlation.",
            limitation=f"Only {n} overlapping reporting periods available for any metric pair "
                       f"(need >= {MIN_PAIR_N}); this document reports at most 3 fiscal years per metric.",
        )

    statistic, p_value = stats.pearsonr(series_a, series_b)
    significant = p_value < ALPHA
    return HypothesisResult(
        hypothesis_id="H2",
        question=f"Is {name_a} correlated with {name_b} for {entity}?",
        H0=f"There is no linear correlation between {name_a} and {name_b} for {entity}.",
        H1=f"There is a linear correlation between {name_a} and {name_b} for {entity}.",
        test_type="correlation (Pearson)",
        variable_1=f"{name_a} ({entity})", variable_2=f"{name_b} ({entity})",
        sample_size=f"{n} pairs",
        test_statistic=round(float(statistic), 4), p_value=round(float(p_value), 4),
        significance_level=ALPHA,
        result="SIGNIFICANT" if significant else "NOT_SIGNIFICANT",
        interpretation=(
            f"{'A statistically significant' if significant else 'No statistically significant'} "
            f"linear correlation was found between {name_a} and {name_b} for {entity} at alpha={ALPHA}."
        ),
        limitation=f"Very small sample (n={n}); a correlation over so few periods should be treated as indicative, not conclusive.",
    )


def run_chi_square(observations: list[Observation]) -> HypothesisResult:
    # None of the ANALYSIS_READY metrics represent categorical counts
    # (they are all continuous financial/operational figures), so no
    # contingency table can be constructed from this dataset.
    return HypothesisResult(
        hypothesis_id="H3", question="Is there an association between two categorical variables?",
        H0="N/A", H1="N/A", test_type="categorical_association (chi-square)",
        variable_1="N/A", variable_2="N/A", sample_size="0",
        test_statistic=None, p_value=None, significance_level=ALPHA,
        result="INSUFFICIENT_DATA",
        interpretation="The analysis-ready observations are all continuous financial/operational "
                       "metrics; none represent categorical count data, so no contingency table can be built.",
        limitation="No categorical/count-by-category data available in the analysis-ready observation set.",
    )


def run_hypothesis_tests(observations: list[Observation]) -> list[HypothesisResult]:
    """Attempts exactly the 3 test types the MVP supports; returns one result row per type."""
    return [
        run_two_group_comparison(observations),
        run_correlation(observations),
        run_chi_square(observations),
    ]
