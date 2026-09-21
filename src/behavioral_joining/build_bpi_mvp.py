"""
build_bpi_mvp.py -- ABIDS MVP OPERATIONAL PRIORITY INDEX.

Explicit, transparent, EQUAL-WEIGHTED business rule for demonstration and
prioritization. NOT externally validated as a universal scientific weighting
model -- that distinction is preserved in every output this module produces.

BPI_MVP = 0.50 * Leakage_Intensity + 0.50 * Behavior_Intensity

Both components are min-max normalized against the OBSERVED stage range in
this dataset. Priority bands are percentile-based (relative), not fixed.
"""
import pandas as pd

BPI_LABEL = ("This is the ABIDS MVP Operational Priority Index. Equal weighting is a "
             "transparent business rule for demonstration and prioritization and has not yet "
             "been externally validated as a universal scientific weighting model.")


def _minmax(series: pd.Series) -> pd.Series:
    lo, hi = series.min(), series.max()
    if hi == lo:
        return series.apply(lambda x: 0.5)
    return (series - lo) / (hi - lo)


def _band(p):
    if p >= 0.75: return "P1_HIGHEST_ATTENTION"
    if p >= 0.5: return "P2_HIGH"
    if p >= 0.25: return "P3_MODERATE"
    return "P4_LOWER_PRIORITY"


def build_stage_priority(stage_summary_df: pd.DataFrame) -> pd.DataFrame:
    df = stage_summary_df.copy()
    df["leakage_intensity"] = round(_minmax(df.dropoff_rate), 4)
    df["behavior_intensity"] = round(_minmax(df.behavior_penetration_rate), 4)
    df["bpi_mvp_score"] = round(0.5 * df.leakage_intensity + 0.5 * df.behavior_intensity, 4)
    df["relative_priority_band"] = df.bpi_mvp_score.rank(pct=True).apply(_band)

    def quadrant(row):
        high_leak = row.leakage_intensity >= 0.5
        high_beh = row.behavior_intensity >= 0.5
        if high_leak and high_beh: return "HIGH_LEAKAGE_HIGH_BEHAVIOR -- HIGHEST OPERATIONAL ATTENTION"
        if high_leak and not high_beh: return "HIGH_LEAKAGE_LOW_BEHAVIOR -- MORE DIAGNOSIS NEEDED"
        if not high_leak and high_beh: return "LOW_LEAKAGE_HIGH_BEHAVIOR -- BEHAVIORALLY ACTIVE, MONITOR"
        return "LOW_LEAKAGE_LOW_BEHAVIOR -- LOWER CURRENT PRIORITY"
    df["quadrant"] = df.apply(quadrant, axis=1)
    df["methodology_note"] = BPI_LABEL
    return df[["journey_stage", "dropoff_rate", "behavior_penetration_rate", "leakage_intensity",
               "behavior_intensity", "bpi_mvp_score", "relative_priority_band", "quadrant",
               "methodology_note"]].sort_values("bpi_mvp_score", ascending=False)


def build_stage_scenario_behavior_priority(stage_scenario_matrix_df: pd.DataFrame) -> pd.DataFrame:
    df = stage_scenario_matrix_df.copy()
    df["leakage_intensity"] = round(_minmax(df.associated_dropoff_rate), 4)
    df["behavior_intensity"] = round(_minmax(df.scenario_share_within_stage), 4)
    df["bpi_mvp_score"] = round(0.5 * df.leakage_intensity + 0.5 * df.behavior_intensity, 4)
    df["relative_priority_band"] = df.bpi_mvp_score.rank(pct=True).apply(_band)
    return df.sort_values("bpi_mvp_score", ascending=False)
