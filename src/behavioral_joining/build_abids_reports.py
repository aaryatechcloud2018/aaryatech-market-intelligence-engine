"""build_abids_reports.py -- FINAL DEMONSTRATION RUN. Builds the six ABIDS report
tables (CSV) from scenario_library, bridge, behavior_outcome, hypotheses, and
statistical_results. BPI priority_score and formal Intelligence State are left
as METHODOLOGY_PENDING throughout -- never invented."""
import pandas as pd

METHODOLOGY_PENDING = "METHODOLOGY_PENDING"


def build_leakage_map(scenarios, bridge, outcome, hypotheses, stat_results):
    rows = []
    for (mech_id, mech_name), sub in scenarios.groupby(["mechanism_id", "mechanism_name"]):
        stage_counts = sub.journey_stage.value_counts()
        hyp = hypotheses[hypotheses.mechanism_id == mech_id]
        stat = stat_results[stat_results.hypothesis_id.isin(hyp.hypothesis_id)] if len(hyp) else pd.DataFrame()
        for stage, n in stage_counts.items():
            row = {
                "mechanism_id": mech_id, "mechanism_name": mech_name, "journey_stage": stage,
                "evidence_count_at_stage": n, "total_evidence_count": len(sub),
                "human_reviewed_share": round((sub.mapping_source == "HUMAN_REVIEWED").mean(), 3),
            }
            if len(stat):
                row["outcome_association_tested"] = stat.iloc[0].result_direction
                row["evidence_grade"] = stat.iloc[0].evidence_grade
                row["p_value"] = stat.iloc[0].p_value
            else:
                row["outcome_association_tested"] = "not tested"
                row["evidence_grade"] = "not tested"
                row["p_value"] = ""
            rows.append(row)
    return pd.DataFrame(rows)


def build_priority_index(scenarios, bridge, hypotheses, stat_results):
    rows = []
    for (mech_id, mech_name), sub in scenarios.groupby(["mechanism_id", "mechanism_name"]):
        n_apps = bridge[bridge.mechanism_id == mech_id].application_id.nunique()
        hyp = hypotheses[hypotheses.mechanism_id == mech_id]
        stat = stat_results[stat_results.hypothesis_id.isin(hyp.hypothesis_id)] if len(hyp) else pd.DataFrame()
        dominant_stage = sub.journey_stage.mode().iloc[0] if len(sub) else "unknown"
        rows.append({
            "mechanism_id": mech_id, "mechanism_name": mech_name,
            "behavior_prevalence_evidence_count": len(sub), "applications_affected": n_apps,
            "dominant_journey_stage": dominant_stage,
            "evidence_strength": stat.iloc[0].evidence_grade if len(stat) else "not tested",
            "effect_size": stat.iloc[0].effect_size if len(stat) else "",
            "statistical_p_value": stat.iloc[0].p_value if len(stat) else "",
            "human_reviewed_share": round((sub.mapping_source == "HUMAN_REVIEWED").mean(), 3),
            "priority_score": METHODOLOGY_PENDING, "priority_band": METHODOLOGY_PENDING,
        })
    return pd.DataFrame(rows).sort_values("applications_affected", ascending=False)


def build_uncertainty_matrix(scenarios, hypotheses, stat_results):
    rows = []
    for (mech_id, mech_name), sub in scenarios.groupby(["mechanism_id", "mechanism_name"]):
        hyp = hypotheses[hypotheses.mechanism_id == mech_id]
        stat = stat_results[stat_results.hypothesis_id.isin(hyp.hypothesis_id)] if len(hyp) else pd.DataFrame()
        n_info_gaps = (sub.information_gap != "None identified from current evidence.").sum()
        if len(stat):
            stage_label = "CORRELATION_TESTED"; evidence_grade = stat.iloc[0].evidence_grade; p_val = stat.iloc[0].p_value
        elif len(hyp):
            stage_label = "HYPOTHESIS_PROPOSED_NOT_TESTED"; evidence_grade = "not tested"; p_val = ""
        else:
            stage_label = "OBSERVATION_ONLY"; evidence_grade = "not tested"; p_val = ""
        rows.append({
            "mechanism_id": mech_id, "mechanism_name": mech_name, "evidence_count": len(sub),
            "human_reviewed_count": (sub.mapping_source == "HUMAN_REVIEWED").sum(),
            "model_applied_count": (sub.mapping_source == "MODEL_APPLIED_FROM_CALIBRATED_FRAMEWORK").sum(),
            "records_with_alternative_interpretation": n_info_gaps,
            "statistical_evidence_stage": stage_label, "evidence_grade": evidence_grade, "p_value": p_val,
            "formal_intelligence_state": METHODOLOGY_PENDING,
            "missing_information": "Held-out replication not yet run; segment-level stratification not yet performed." if len(stat) else "Not yet statistically tested.",
        })
    return pd.DataFrame(rows)


def build_scenario_matrix(scenarios):
    cols = ["mechanism_id", "mechanism_name", "scenario_name", "observable_evidence",
            "journey_stage", "alternative_explanation", "information_gap", "outcome_association", "mapping_source"]
    return scenarios[cols].copy()


def build_journey_map(scenarios, hypotheses, stat_results):
    rows = []
    for stage, sub in scenarios.groupby("journey_stage"):
        mechs = sub.mechanism_id.unique()
        hyp = hypotheses[hypotheses.mechanism_id.isin(mechs)]
        stat = stat_results[stat_results.hypothesis_id.isin(hyp.hypothesis_id)]
        rows.append({
            "journey_stage": stage, "mechanisms_observed": ";".join(sorted(sub.mechanism_id.unique())),
            "scenario_count": len(sub), "evidence_frequency": len(sub), "priority_band": METHODOLOGY_PENDING,
            "information_gaps_count": (sub.information_gap != "None identified from current evidence.").sum(),
            "tested_mechanisms_at_stage": stat.hypothesis_id.nunique() if len(stat) else 0,
            "potential_intervention_point": "YES -- evidence concentrated here" if len(sub) > 50 else "monitor",
        })
    return pd.DataFrame(rows).sort_values("evidence_frequency", ascending=False)


def build_intervention_matrix(scenarios, hypotheses, stat_results):
    rows = []
    tested_mechs = set(stat_results.merge(hypotheses[["hypothesis_id", "mechanism_id"]], on="hypothesis_id").mechanism_id) if len(stat_results) else set()
    for mech_id in tested_mechs:
        mech_name = scenarios[scenarios.mechanism_id == mech_id].mechanism_name.iloc[0]
        hyp = hypotheses[hypotheses.mechanism_id == mech_id].iloc[0]
        stat = stat_results[stat_results.hypothesis_id == hyp.hypothesis_id].iloc[0]
        dominant_stage = scenarios[scenarios.mechanism_id == mech_id].journey_stage.mode().iloc[0]
        rows.append({
            "mechanism_id": mech_id, "mechanism_name": mech_name,
            "what_we_know": f"{stat.evidence_grade} evidence ({stat.test_name}, p={stat.p_value:.4f}, "
                             f"adjusted p={stat.adjusted_p_value:.4f}); direction: {stat.result_direction}.",
            "what_we_dont_know": "Whether this association replicates on held-out data (not yet run); "
                                  "whether it is causal; whether it holds within specific client segments.",
            "recruiter_question": f"When you notice evidence resembling '{mech_name}' around {dominant_stage}, "
                                    f"ask an open follow-up question rather than assuming intent.",
            "recruiter_response": "Investigate the specific situation; do not treat this pattern as predictive "
                                    "of any individual candidate's decision.",
            "process_intervention": "Candidate for a recruiter coaching note; not yet piloted.",
            "marketing_intervention": "Candidate for messaging review at this journey stage; not yet piloted.",
            "measurement_plan": "Not yet designed -- requires a defined pilot with pre/post or test/control comparison.",
            "result": "NOT YET TESTED", "learning": "Pending intervention pilot.",
        })
    return pd.DataFrame(rows)
