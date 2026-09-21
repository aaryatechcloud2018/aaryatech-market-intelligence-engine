"""
build_client_data_mart.py -- CLIENT INTELLIGENCE / VISUALIZATION LAYER ONLY.

Builds clean, reproducible reporting tables from the ALREADY-COMPLETED and
verified ABIDS final analysis (behavioral_mappings.csv, scenario_library.csv,
application_behavior_mechanisms.csv, behavior_outcome_dataset.csv,
abids_hypotheses.csv, abids_statistical_results.csv). No evidence extraction,
mapping, scenario generation, or hypothesis/statistical work is redone here --
this module only aggregates and reshapes existing, verified outputs.

SCOPE NOTE: behavioral evidence only exists on the discovery split (evidence
extraction was never run on hypothesis_generation or held_out_test). To keep
every numerator and denominator drawn from the SAME population and avoid any
population-mismatch inflation, every stage/behavior table in this data mart
is scoped to the discovery split only (N=1,499 applications). held_out_test
is never read.

NO_SUPPORTED_MECHANISM rows (empty mechanism_id) are excluded from every
"behavior" count in this data mart -- they are not a behavior.
"""
import pandas as pd
import numpy as np

RAW = "data/behavioral_joining/raw/"
FINAL = "data/behavioral_joining/processed/final/"

FUNNEL_STAGES = [
    "screened", "submitted", "client_interview_1", "offer_extended",
    "offer_accepted", "background_check", "onboarding_docs_sent", "start_date",
]
NON_JOINED_DISPOSITIONS = {"accepted_no_show", "withdrew_post_acceptance", "declined_offer", "rejected_by_client"}
JOINED_DISPOSITIONS = {"joined_on_time", "joined_late"}


def load_all():
    apps = pd.read_csv(RAW + "01_candidate_applications.csv", keep_default_na=False)
    stages = pd.read_csv(RAW + "03_stage_events.csv", keep_default_na=False)
    mappings_full = pd.read_csv(FINAL + "behavioral_mappings.csv", keep_default_na=False)
    scenarios = pd.read_csv(FINAL + "scenario_library.csv", keep_default_na=False)
    bridge = pd.read_csv(FINAL + "application_behavior_mechanisms.csv", keep_default_na=False)
    hyps = pd.read_csv(FINAL + "abids_hypotheses.csv", keep_default_na=False)
    stats = pd.read_csv(FINAL + "abids_statistical_results.csv", keep_default_na=False)

    discovery_ids = set(apps[apps.research_split == "discovery"].application_id)
    stages = stages[stages.application_id.isin(discovery_ids)].copy()
    mappings = mappings_full[mappings_full.application_id.isin(discovery_ids)].copy()

    return {"apps": apps, "stages": stages, "mappings": mappings, "scenarios": scenarios,
            "bridge": bridge, "hyps": hyps, "stats": stats, "discovery_ids": discovery_ids}


def build_stage_summary(D):
    apps, stages, mappings, discovery_ids = D["apps"], D["stages"], D["mappings"], D["discovery_ids"]
    supported = mappings[mappings.mechanism_id.astype(str).str.len() > 0]

    rows = []
    for i, stage in enumerate(FUNNEL_STAGES):
        entering_apps = set(stages[stages.stage_name == stage].application_id)
        n_entering = len(entering_apps)
        if i < len(FUNNEL_STAGES) - 1:
            next_stage = FUNNEL_STAGES[i + 1]
            exiting_apps = entering_apps & set(stages[stages.stage_name == next_stage].application_id)
        else:
            exiting_apps = entering_apps
        n_exiting = len(exiting_apps)
        dropoff = n_entering - n_exiting
        dropoff_rate = dropoff / n_entering if n_entering else 0.0

        ev_at_stage = mappings[mappings.journey_stage == stage]
        supported_at_stage = supported[supported.journey_stage == stage]
        apps_with_behavior = supported_at_stage.application_id.nunique()
        behavior_penetration = apps_with_behavior / n_entering if n_entering else 0.0
        scenario_count = supported_at_stage.evidence_id.nunique()
        info_gap_count = int((ev_at_stage.information_gap != "None identified from current evidence.").sum())
        info_gap_rate = info_gap_count / len(ev_at_stage) if len(ev_at_stage) else 0.0

        rows.append({
            "journey_stage": stage,
            "applications_entering_stage": n_entering,
            "applications_exiting_stage": n_exiting,
            "dropoff_count": dropoff,
            "dropoff_rate": round(dropoff_rate, 4),
            "behavior_evidence_count": len(ev_at_stage),
            "applications_with_behavior": apps_with_behavior,
            "behavior_penetration_rate": round(behavior_penetration, 4),
            "scenario_count": scenario_count,
            "information_gap_count": info_gap_count,
            "information_gap_rate": round(info_gap_rate, 4),
        })
    return pd.DataFrame(rows)


def build_stage_behavior_matrix(D):
    mappings, apps = D["mappings"], D["apps"]
    disp = apps.set_index("application_id").final_disposition
    supported = mappings[mappings.mechanism_id.astype(str).str.len() > 0]

    rows = []
    for stage, sub in supported.groupby("journey_stage"):
        stage_total_apps = sub.application_id.nunique()
        for (mech_id, mech_name), msub in sub.groupby(["mechanism_id", "mechanism_name"]):
            app_ids = msub.application_id.unique()
            apps_with = len(app_ids)
            share = apps_with / stage_total_apps if stage_total_apps else 0.0
            n_dropoff = sum(1 for a in app_ids if disp.get(a) in NON_JOINED_DISPOSITIONS)
            rows.append({
                "journey_stage": stage, "mechanism_id": mech_id, "mechanism_name": mech_name,
                "applications_with_behavior": apps_with,
                "behavior_share_within_stage": round(share, 4),
                "dropoff_count_associated": n_dropoff,
                "dropoff_rate_associated": round(n_dropoff / apps_with, 4) if apps_with else 0.0,
            })
    return pd.DataFrame(rows)


def build_stage_scenario_matrix(D):
    mappings, apps = D["mappings"], D["apps"]
    disp = apps.set_index("application_id").final_disposition
    supported = mappings[mappings.mechanism_id.astype(str).str.len() > 0].copy()

    rows = []
    for stage, sub in supported.groupby("journey_stage"):
        stage_total_evidence = len(sub)
        for (mech_id, mech_name), msub in sub.groupby(["mechanism_id", "mechanism_name"]):
            scenario_name = f"{mech_name} \u2014 {stage}"
            app_ids = msub.application_id.unique()
            n_apps = len(app_ids)
            share = len(msub) / stage_total_evidence if stage_total_evidence else 0.0
            n_dropoff = sum(1 for a in app_ids if disp.get(a) in NON_JOINED_DISPOSITIONS)
            info_gap_count = int((msub.information_gap != "None identified from current evidence.").sum())
            rows.append({
                "journey_stage": stage, "scenario_id": f"AGG-{mech_id}-{stage}", "scenario_name": scenario_name,
                "mechanism_id": mech_id, "mechanism_name": mech_name,
                "applications_observed": n_apps,
                "scenario_share_within_stage": round(share, 4),
                "associated_dropoff_count": n_dropoff,
                "associated_dropoff_rate": round(n_dropoff / n_apps, 4) if n_apps else 0.0,
                "information_gap_count": info_gap_count,
            })
    return pd.DataFrame(rows)


def build_stage_behavior_scenario_map(D):
    mappings, apps = D["mappings"], D["apps"]
    disp = apps.set_index("application_id").final_disposition
    supported = mappings[mappings.mechanism_id.astype(str).str.len() > 0].copy()
    supported["outcome"] = supported.application_id.map(disp)
    supported["dropoff"] = supported.outcome.isin(NON_JOINED_DISPOSITIONS)
    cols = ["journey_stage", "mechanism_id", "mechanism_name", "application_id", "evidence_id",
            "outcome", "dropoff", "mapping_source"]
    return supported[cols].reset_index(drop=True)


def build_uncertainty_stage_summary(stage_summary_df):
    df = stage_summary_df.copy()
    df["evidence_available"] = df.behavior_evidence_count > 0
    coverage = df.behavior_penetration_rate * (1 - df.information_gap_rate)
    df["uncertainty_score"] = round(df.dropoff_rate * (1 - coverage), 4)

    q = df.uncertainty_score.rank(pct=True)
    def band(p):
        if p >= 0.75: return "CRITICAL_INTELLIGENCE_GAP"
        if p >= 0.5: return "MODERATE_GAP"
        if p >= 0.25: return "DIAGNOSABLE"
        return "WELL_UNDERSTOOD"
    df["uncertainty_band"] = q.apply(band)
    df["uncertainty_reason"] = df.apply(
        lambda r: f"dropoff_rate={r.dropoff_rate:.0%}, behavior_penetration={r.behavior_penetration_rate:.0%}, "
                  f"information_gap_rate={r.information_gap_rate:.0%}", axis=1
    )
    return df[["journey_stage", "dropoff_count", "dropoff_rate", "evidence_available",
                "information_gap_count", "information_gap_rate", "uncertainty_score",
                "uncertainty_band", "uncertainty_reason"]]


def build_hypothesis_visual_summary(D):
    hyps, stats, apps, bridge = D["hyps"], D["stats"], D["apps"], D["bridge"]
    pop = apps[(apps.offer_accepted.astype(str) == "True") &
               (apps.research_split.isin(["discovery", "hypothesis_generation"]))].copy()
    pop["joined"] = pop.final_disposition.isin(JOINED_DISPOSITIONS)

    merged = hyps.merge(stats, on="hypothesis_id", how="inner", suffixes=("_hyp", ""))
    rows = []
    for _, h in merged.iterrows():
        mech_id = h.mechanism_id
        with_mech = set(bridge[bridge.mechanism_id == mech_id].application_id)
        pop["has_mechanism"] = pop.application_id.isin(with_mech)
        g = pop[pop.has_mechanism]
        c = pop[~pop.has_mechanism]
        group_n, comparison_n = len(g), len(c)
        group_rate = g.joined.mean() if group_n else float("nan")
        comparison_rate = c.joined.mean() if comparison_n else float("nan")
        abs_diff = group_rate - comparison_rate if group_n and comparison_n else float("nan")

        rows.append({
            "hypothesis_id": h.hypothesis_id, "mechanism_id": mech_id,
            "mechanism_name": h.mechanism_name, "scenario_id": h.get("scenario_id", ""),
            "comparison_group": h.comparison_group, "outcome": h.outcome_variable,
            "group_n": group_n, "comparison_n": comparison_n,
            "group_outcome_rate": round(group_rate, 4), "comparison_outcome_rate": round(comparison_rate, 4),
            "absolute_difference": round(abs_diff, 4),
            "effect_size": h.effect_size, "effect_size_metric": h.effect_size_metric,
            "confidence_interval": h.confidence_interval, "adjusted_p_value": h.adjusted_p_value,
            "evidence_grade": h.evidence_grade,
            "plain_english_interpretation": (
                f"Applications with approved {h.mechanism_name} evidence showed a "
                f"{group_rate:.0%} joining rate, versus {comparison_rate:.0%} for the comparison group, "
                f"in the current analytical sample. Association only -- not a causal claim."
            ),
        })
    return pd.DataFrame(rows)


def build_all_and_save(out_dir="reports/behavioral_joining/client_intelligence/data/"):
    D = load_all()
    stage_summary = build_stage_summary(D)
    stage_behavior_matrix = build_stage_behavior_matrix(D)
    stage_scenario_matrix = build_stage_scenario_matrix(D)
    stage_behavior_scenario_map = build_stage_behavior_scenario_map(D)
    uncertainty_stage_summary = build_uncertainty_stage_summary(stage_summary)
    hypothesis_visual_summary = build_hypothesis_visual_summary(D)

    tables = {
        "stage_summary": stage_summary,
        "stage_behavior_matrix": stage_behavior_matrix,
        "stage_scenario_matrix": stage_scenario_matrix,
        "stage_behavior_scenario_map": stage_behavior_scenario_map,
        "uncertainty_stage_summary": uncertainty_stage_summary,
        "hypothesis_visual_summary": hypothesis_visual_summary,
    }
    for name, df in tables.items():
        df.to_csv(f"{out_dir}{name}.csv", index=False)
    return tables, D


if __name__ == "__main__":
    tables, D = build_all_and_save()
    for name, df in tables.items():
        print(name, df.shape)
