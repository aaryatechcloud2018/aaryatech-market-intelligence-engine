"""build_client_pdfs.py -- Power BI-style client PDF reports, Parts 2-9."""
import sys
sys.path.insert(0, ".")
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from src.behavioral_joining.chart_helpers import *

d = pickle.load(open("/tmp/client_intel_data.pkl", "rb"))
tables, bpi_stage, bpi_detail, apps_summary = d["tables"], d["bpi_stage"], d["bpi_detail"], d["apps_summary"]

OUT = "reports/behavioral_joining/client_intelligence"
STAGES = tables["stage_summary"].journey_stage.tolist()

ASSOC_NOTE = ('Wording note: this report uses "associated with" / "observed alongside" / "appears in '
              'applications with" throughout. It never claims a behavior causes a candidate outcome.')
BG_CHECK_CAVEAT = ("Note: drop-off at background_check and onboarding_docs_sent partially reflects "
                    "optional stage events that were not recorded for some applications that still "
                    "continued, not only genuine withdrawal -- see internal QA report for detail.")


def stage_label(s):
    return s.replace("_", " ").title()


def build_journey_map_pdf():
    ss = tables["stage_summary"]
    with PdfPages(f"{OUT}/02_ABIDS_Behavioral_Journey_Map.pdf") as pdf:
        fig = new_page()
        title_block(fig, "Aaryatech\u2122 Behavioral Journey Map", "Where and when behavioral patterns emerge")
        kpi_cards(fig, [
            ("Stages Tracked", len(ss)),
            ("Peak Drop-off Stage", stage_label(ss.loc[ss.dropoff_rate.idxmax(), "journey_stage"])),
            ("Peak Behavior Penetration", stage_label(ss.loc[ss.behavior_penetration_rate.idxmax(), "journey_stage"])),
        ])
        ax1 = fig.add_axes([0.08, 0.40, 0.4, 0.30])
        funnel_chart(ax1, [stage_label(s) for s in ss.journey_stage], ss.applications_entering_stage.tolist())
        ax2 = fig.add_axes([0.56, 0.40, 0.4, 0.30])
        dropoff_chart(ax2, [stage_label(s) for s in ss.journey_stage], ss.dropoff_rate.tolist())
        ax3 = fig.add_axes([0.08, 0.08, 0.4, 0.24])
        bar_chart(ax3, [stage_label(s) for s in ss.journey_stage], (ss.behavior_penetration_rate * 100).tolist(),
                  "Behavior Penetration % by Stage", color=GOLD, fmt="{:.0f}%")
        top_mech = tables["stage_behavior_matrix"].groupby("mechanism_name").applications_with_behavior.sum().sort_values(ascending=False).head(6)
        ax4 = fig.add_axes([0.56, 0.08, 0.4, 0.24])
        bar_chart(ax4, top_mech.index.tolist(), top_mech.values.tolist(), "Top Behaviors (All Stages)", color=NAVY)
        footer(fig, "Page 1 of 2")
        pdf.savefig(fig); plt.close(fig)

        fig = new_page()
        title_block(fig, "Stage \u00d7 Behavior Heatmap", "% of applications at each stage with each behavior")
        sbm = tables["stage_behavior_matrix"]
        top_mechs = sbm.groupby("mechanism_name").applications_with_behavior.sum().sort_values(ascending=False).head(10).index.tolist()
        pivot = sbm[sbm.mechanism_name.isin(top_mechs)].pivot_table(
            index="journey_stage", columns="mechanism_name", values="behavior_share_within_stage", fill_value=0
        ).reindex(STAGES).fillna(0)
        pivot = pivot[top_mechs]
        ax = fig.add_axes([0.28, 0.15, 0.66, 0.65])
        heatmap(ax, pivot.values, [stage_label(s) for s in pivot.index], pivot.columns.tolist(),
                "Stage \u00d7 Behavior: Share of Applications")
        note_text(fig, "Client question this answers: at which stages are behaviors appearing most strongly?")
        footer(fig, "Page 2 of 2")
        pdf.savefig(fig); plt.close(fig)


def build_leakage_map_pdf():
    ss = tables["stage_summary"]
    sbm = tables["stage_behavior_matrix"]
    with PdfPages(f"{OUT}/03_ABIDS_Behavioral_Leakage_Map.pdf") as pdf:
        fig = new_page()
        title_block(fig, "Aaryatech\u2122 Behavioral Leakage Map", "Where are we losing candidates, and what behavioral situations appear alongside it?")
        kpi_cards(fig, [
            ("Total Drop-off (Discovery)", int(ss.dropoff_count.sum())),
            ("Highest-Leakage Stage", stage_label(ss.loc[ss.dropoff_rate.idxmax(), "journey_stage"])),
            ("Peak Drop-off Rate", f"{ss.dropoff_rate.max():.0%}"),
        ])
        ax1 = fig.add_axes([0.08, 0.42, 0.84, 0.26])
        dropoff_chart(ax1, [stage_label(s) for s in ss.journey_stage], ss.dropoff_rate.tolist())
        top_mechs = sbm.groupby("mechanism_name").dropoff_count_associated.sum().sort_values(ascending=False).head(8)
        ax2 = fig.add_axes([0.08, 0.10, 0.84, 0.24])
        bar_chart(ax2, top_mechs.index.tolist(), top_mechs.values.tolist(),
                  "Top Behavioral Leakage Scenarios (associated drop-off count, all stages)", color=RED)
        note_text(fig, ASSOC_NOTE)
        footer(fig, "Page 1 of 2")
        pdf.savefig(fig); plt.close(fig)

        fig = new_page()
        title_block(fig, "Behavioral Leakage Heatmap", "Stage \u00d7 Behavior: associated drop-off rate")
        top_mechs2 = sbm.groupby("mechanism_name").applications_with_behavior.sum().sort_values(ascending=False).head(10).index.tolist()
        pivot = sbm[sbm.mechanism_name.isin(top_mechs2)].pivot_table(
            index="journey_stage", columns="mechanism_name", values="dropoff_rate_associated", fill_value=0
        ).reindex(STAGES).fillna(0)[top_mechs2]
        ax = fig.add_axes([0.28, 0.42, 0.66, 0.4])
        heatmap(ax, pivot.values, [stage_label(s) for s in pivot.index], pivot.columns.tolist(),
                "Stage \u00d7 Behavior: Associated Drop-off Rate", cmap="Reds")
        note_text(fig, "Reads as: of applications AT this stage WITH this behavior, this share ended in a non-join disposition. " + ASSOC_NOTE, y=0.30)
        note_text(fig, BG_CHECK_CAVEAT, y=0.24)
        footer(fig, "Page 2 of 2")
        pdf.savefig(fig); plt.close(fig)


def build_priority_matrix_pdf():
    with PdfPages(f"{OUT}/04_ABIDS_Behavioral_Priority_Matrix.pdf") as pdf:
        fig = new_page()
        title_block(fig, "Aaryatech\u2122 Behavioral Priority Index (BPI\u2122 MVP)", "Where should management focus first?")
        kpi_cards(fig, [
            ("Highest Priority Stage", stage_label(bpi_stage.iloc[0].journey_stage)),
            ("BPI MVP Score", f"{bpi_stage.iloc[0].bpi_mvp_score:.2f}"),
            ("Formula", "50% Leakage + 50% Behavior"),
        ])
        ax1 = fig.add_axes([0.08, 0.42, 0.84, 0.26])
        bar_chart(ax1, [stage_label(s) for s in bpi_stage.journey_stage], bpi_stage.bpi_mvp_score.tolist(),
                  "BPI MVP Score by Stage (higher = more operational attention)", color=NAVY, fmt="{:.2f}")
        ax2 = fig.add_axes([0.1, 0.08, 0.5, 0.26])
        quadrant_chart(ax2, bpi_stage.behavior_intensity.tolist(), bpi_stage.leakage_intensity.tolist(),
                       [stage_label(s) for s in bpi_stage.journey_stage],
                       "2\u00d72 Priority Matrix", "Behavioral Intensity \u2192", "Leakage Intensity \u2192",
                       ["HIGH LEAKAGE\nLOW BEHAVIOR", "HIGHEST\nATTENTION", "LOWER\nPRIORITY", "BEHAVIORALLY\nACTIVE"])
        note_text(fig, ("This is the ABIDS MVP Operational Priority Index. Equal weighting is a transparent business "
                        "rule for demonstration and prioritization and has not yet been externally validated as a "
                        "universal scientific weighting model."), y=0.04)
        footer(fig, "Page 1 of 2")
        pdf.savefig(fig); plt.close(fig)

        fig = new_page()
        title_block(fig, "Stage \u00d7 Scenario \u00d7 Behavior Priority Matrix", "Detail-level ranking (top 15 by BPI MVP score)")
        top = bpi_detail.head(15)
        ax = fig.add_axes([0.06, 0.1, 0.88, 0.75])
        ax.axis("off")
        col_labels = ["Stage", "Mechanism", "Applications", "Drop-off %", "BPI Score", "Band"]
        cell_text = [[stage_label(r.journey_stage), r.mechanism_name, str(r.applications_observed),
                      f"{r.associated_dropoff_rate:.0%}", f"{r.bpi_mvp_score:.2f}", r.relative_priority_band]
                     for r in top.itertuples()]
        tbl = ax.table(cellText=cell_text, colLabels=col_labels, loc="center", cellLoc="left")
        tbl.auto_set_font_size(False); tbl.set_fontsize(8); tbl.scale(1, 1.6)
        for j in range(len(col_labels)):
            tbl[0, j].set_facecolor(NAVY); tbl[0, j].set_text_props(color="white", fontweight="bold")
        footer(fig, "Page 2 of 2")
        pdf.savefig(fig); plt.close(fig)


def build_uncertainty_matrix_pdf():
    unc = tables["uncertainty_stage_summary"]
    with PdfPages(f"{OUT}/05_ABIDS_Behavioral_Uncertainty_Matrix.pdf") as pdf:
        fig = new_page()
        title_block(fig, "Aaryatech\u2122 Behavioral Uncertainty Matrix", "Where are we losing candidates but know the least about why?")
        critical = unc[unc.uncertainty_band == "CRITICAL_INTELLIGENCE_GAP"]
        kpi_cards(fig, [
            ("Critical Gap Stages", len(critical)),
            ("Highest Uncertainty", stage_label(unc.loc[unc.uncertainty_score.idxmax(), "journey_stage"])),
            ("Avg Information Gap Rate", f"{unc.information_gap_rate.mean():.0%}"),
        ])
        info_coverage = 1 - unc.information_gap_rate
        ax = fig.add_axes([0.12, 0.40, 0.5, 0.28])
        quadrant_chart(ax, info_coverage.tolist(), unc.dropoff_rate.tolist(),
                       [stage_label(s) for s in unc.journey_stage],
                       "2\u00d72 Uncertainty Matrix", "Information Coverage \u2192", "Drop-off Intensity \u2192",
                       ["CRITICAL GAP", "DIAGNOSABLE", "MONITOR/\nDATA GAP", "WELL\nUNDERSTOOD"])
        ax2 = fig.add_axes([0.66, 0.40, 0.28, 0.28])
        bar_chart(ax2, [stage_label(s) for s in unc.journey_stage], (unc.uncertainty_score * 100).tolist(),
                  "Uncertainty Score by Stage", color=RED, fmt="{:.0f}")
        ax3 = fig.add_axes([0.1, 0.08, 0.84, 0.24])
        bar_chart(ax3, [stage_label(s) for s in unc.journey_stage], (unc.information_gap_rate * 100).tolist(),
                  "Information Gap % by Stage", color=GOLD, fmt="{:.0f}%")
        footer(fig, "Page 1 of 2")
        pdf.savefig(fig); plt.close(fig)

        fig = new_page()
        title_block(fig, "Recruiter Data-Collection Recommendations", "For the highest-uncertainty stages")
        top_unc = unc.sort_values("uncertainty_score", ascending=False).head(4)
        y = 0.80
        for r in top_unc.itertuples():
            fig.text(0.06, y, f"{stage_label(r.journey_stage)} -- {r.uncertainty_band}", fontsize=13, fontweight="bold", color=NAVY)
            fig.text(0.08, y - 0.035, r.uncertainty_reason, fontsize=9, color="#333333")
            fig.text(0.08, y - 0.065, "Recommendation: capture more structured recruiter notes at this stage "
                                        "before drawing conclusions; do not infer missing information.", fontsize=9, color=GRAY, style="italic")
            y -= 0.14
        footer(fig, "Page 2 of 2")
        pdf.savefig(fig); plt.close(fig)


def build_scenario_matrix_pdf():
    ssm = tables["stage_scenario_matrix"]
    with PdfPages(f"{OUT}/06_ABIDS_Candidate_Scenario_Matrix.pdf") as pdf:
        fig = new_page()
        title_block(fig, "Aaryatech\u2122 Candidate Scenario Matrix", "What real situations do recruiters encounter, and what behaviors are associated?")
        top_scn = ssm.sort_values("applications_observed", ascending=False).head(8)
        kpi_cards(fig, [
            ("Distinct Scenarios", len(ssm)),
            ("Top Scenario", top_scn.iloc[0].scenario_name[:24]),
            ("Applications Observed (top)", int(top_scn.iloc[0].applications_observed)),
        ])
        ax1 = fig.add_axes([0.08, 0.42, 0.84, 0.28])
        bar_chart(ax1, top_scn.scenario_name.str.slice(0, 30).tolist(), top_scn.applications_observed.tolist(),
                  "Top Scenarios by Application Count", color=NAVY)
        pivot = ssm.pivot_table(index="journey_stage", columns="mechanism_name", values="applications_observed", fill_value=0).reindex(STAGES).fillna(0)
        top_cols = pivot.sum().sort_values(ascending=False).head(8).index
        ax2 = fig.add_axes([0.28, 0.06, 0.66, 0.28])
        heatmap(ax2, pivot[top_cols].values, [stage_label(s) for s in pivot.index], list(top_cols),
                "Stage \u00d7 Scenario Heatmap (applications)", cmap="Blues", fmt="{:.0f}")
        footer(fig, "Page 1 of 2")
        pdf.savefig(fig); plt.close(fig)

        fig = new_page()
        title_block(fig, "Scenario Outcome Comparison", "Associated drop-off % for top scenarios")
        ax = fig.add_axes([0.1, 0.15, 0.8, 0.65])
        bar_chart(ax, top_scn.scenario_name.str.slice(0, 30).tolist(), (top_scn.associated_dropoff_rate * 100).tolist(),
                  "Associated Drop-off % by Scenario", color=RED, fmt="{:.0f}%")
        note_text(fig, ASSOC_NOTE)
        footer(fig, "Page 2 of 2")
        pdf.savefig(fig); plt.close(fig)


def build_intervention_matrix_pdf():
    top_priority = bpi_detail.head(6)
    with PdfPages(f"{OUT}/07_ABIDS_Intervention_Intelligence_Matrix.pdf") as pdf:
        fig = new_page()
        title_block(fig, "Aaryatech\u2122 Intervention Intelligence Matrix", "What should we test doing differently?")
        kpi_cards(fig, [
            ("Priority Scenarios", len(top_priority)),
            ("Highest Priority Stage", stage_label(top_priority.iloc[0].journey_stage)),
            ("Interventions Proposed", len(top_priority)),
        ])
        ax = fig.add_axes([0.04, 0.06, 0.92, 0.70])
        ax.axis("off")
        col_labels = ["Stage", "Behavior", "Recruiter Should Ask", "Test", "KPI to Measure"]
        rows = []
        for r in top_priority.itertuples():
            rows.append([
                stage_label(r.journey_stage), r.mechanism_name,
                f"Open question about {r.mechanism_name.lower()} indicators",
                "Add a structured check-in at this stage (pilot, not yet run)",
                "Change in associated drop-off %",
            ])
        tbl = ax.table(cellText=rows, colLabels=col_labels, loc="center", cellLoc="left")
        tbl.auto_set_font_size(False); tbl.set_fontsize(7.5); tbl.scale(1, 2.2)
        for j in range(len(col_labels)):
            tbl[0, j].set_facecolor(NAVY); tbl[0, j].set_text_props(color="white", fontweight="bold")
        note_text(fig, "Interventions are recommendations to TEST, not claims of guaranteed improvement. None have been piloted yet.", y=0.04)
        footer(fig, "Page 1 of 1")
        pdf.savefig(fig); plt.close(fig)


def build_visual_evidence_pdf():
    hv = tables["hypothesis_visual_summary"]
    with PdfPages(f"{OUT}/08_ABIDS_Visual_Evidence_Report.pdf") as pdf:
        fig = new_page()
        title_block(fig, "ABIDS Visual Evidence Report", "Every tested hypothesis, one visual card each")
        kpi_cards(fig, [
            ("Hypotheses Tested", len(hv)),
            ("Supported", int((hv.evidence_grade == "SUPPORTED").sum())),
            ("Weak", int((hv.evidence_grade == "WEAK").sum())),
        ])
        footer(fig, f"Page 1 of {len(hv)+1}")
        pdf.savefig(fig); plt.close(fig)

        for i, r in enumerate(hv.itertuples(), start=2):
            fig = new_page()
            title_block(fig, r.mechanism_name.upper(), f"Hypothesis {r.hypothesis_id}", demo_note=False)
            ax1 = fig.add_axes([0.08, 0.45, 0.35, 0.35])
            bar_chart(ax1, ["Group (with behavior)", "Comparison (without)"],
                      [r.group_outcome_rate * 100, r.comparison_outcome_rate * 100],
                      "Joining Rate Comparison", color=NAVY, horizontal=False, fmt="{:.0f}%")
            ax2 = fig.add_axes([0.5, 0.55, 0.18, 0.18])
            evidence_badge(ax2, r.evidence_grade)
            fig.text(0.72, 0.72, f"Difference: {r.absolute_difference:+.0%} pts", fontsize=12, fontweight="bold", color=NAVY)
            fig.text(0.72, 0.66, f"Sample: n={r.group_n} vs n={r.comparison_n}", fontsize=9, color="#555555")
            fig.text(0.72, 0.61, f"Effect size: {r.effect_size:.3f} ({r.effect_size_metric})", fontsize=9, color="#555555")
            fig.text(0.72, 0.56, f"CI: {r.confidence_interval}", fontsize=9, color="#555555")
            fig.text(0.72, 0.51, f"Adjusted p-value: {r.adjusted_p_value:.4f}", fontsize=9, color="#555555")
            fig.text(0.08, 0.30, "Interpretation:", fontsize=10, fontweight="bold", color=GOLD)
            fig.text(0.08, 0.25, r.plain_english_interpretation, fontsize=9, wrap=True)
            fig.text(0.08, 0.15, "Limitation:", fontsize=10, fontweight="bold", color=RED)
            fig.text(0.08, 0.10, "Association only, on demonstration data. Does not prove causation.", fontsize=9, style="italic", color=GRAY)
            footer(fig, f"Page {i} of {len(hv)+1}")
            pdf.savefig(fig); plt.close(fig)


if __name__ == "__main__":
    build_journey_map_pdf()
    build_leakage_map_pdf()
    build_priority_matrix_pdf()
    build_uncertainty_matrix_pdf()
    build_scenario_matrix_pdf()
    build_intervention_matrix_pdf()
    build_visual_evidence_pdf()
    print("all client PDFs built")
