"""build_executive_dashboard.py -- 01_ABIDS_Executive_Dashboard.pdf"""
import sys
sys.path.insert(0, ".")
import pickle
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from src.behavioral_joining.chart_helpers import *

d = pickle.load(open("/tmp/client_intel_data.pkl", "rb"))
tables, bpi_stage, bpi_detail, apps_summary = d["tables"], d["bpi_stage"], d["bpi_detail"], d["apps_summary"]
OUT = "reports/behavioral_joining/client_intelligence"


def stage_label(s):
    return s.replace("_", " ").title()

STAGE_SHORT = {
    "screened": "Screened", "submitted": "Submitted", "client_interview_1": "Interview 1",
    "offer_extended": "Offer Ext.", "offer_accepted": "Offer Acc.", "background_check": "Bg Check",
    "onboarding_docs_sent": "Onboard Docs", "start_date": "Start Date",
}
def short_stage(s):
    return STAGE_SHORT.get(s, s)


with PdfPages(f"{OUT}/01_ABIDS_Executive_Dashboard.pdf") as pdf:
    fig = new_page()
    title_block(fig, "ABIDS Executive Dashboard", "Behavioral Joining Intelligence -- One-Page Summary")
    kpi_cards(fig, list(apps_summary.items()), y=0.80, height=0.09)

    ss = tables["stage_summary"]
    ax1 = fig.add_axes([0.06, 0.58, 0.26, 0.18])
    funnel_chart(ax1, [short_stage(s) for s in ss.journey_stage], ss.applications_entering_stage.tolist(), xlabel=False)
    ax1.tick_params(axis="y", labelsize=7)
    ax2 = fig.add_axes([0.40, 0.58, 0.26, 0.18])
    dropoff_chart(ax2, [short_stage(s) for s in ss.journey_stage], ss.dropoff_rate.tolist(), xlabel=False)
    ax2.tick_params(axis="y", labelsize=7)

    sbm = tables["stage_behavior_matrix"]
    top_mechs = sbm.groupby("mechanism_name").applications_with_behavior.sum().sort_values(ascending=False).head(6).index.tolist()
    pivot = sbm[sbm.mechanism_name.isin(top_mechs)].pivot_table(
        index="journey_stage", columns="mechanism_name", values="behavior_share_within_stage", fill_value=0
    ).reindex(ss.journey_stage.tolist()).fillna(0)[top_mechs]
    ax3 = fig.add_axes([0.74, 0.58, 0.22, 0.18])
    heatmap(ax3, pivot.values, [short_stage(s) for s in pivot.index], [m[:12] for m in top_mechs], "Stage \u00d7 Behavior")
    ax3.tick_params(axis="both", labelsize=6)

    ax4 = fig.add_axes([0.06, 0.30, 0.24, 0.20])
    quadrant_chart(ax4, bpi_stage.behavior_intensity.tolist(), bpi_stage.leakage_intensity.tolist(),
                   [short_stage(s) for s in bpi_stage.journey_stage],
                   "BPI Priority Matrix", "Behavior \u2192", "Leakage \u2192",
                   ["HIGH LEAK\nLOW BEH", "HIGHEST\nATTN", "LOWER\nPRIORITY", "ACTIVE"])

    top_scn = tables["stage_scenario_matrix"].sort_values("applications_observed", ascending=False).head(5)
    ax5 = fig.add_axes([0.38, 0.30, 0.28, 0.20])
    bar_chart(ax5, top_scn.scenario_name.str.slice(0, 18).tolist(), top_scn.applications_observed.tolist(), "Top Scenarios", color=NAVY)
    ax5.tick_params(axis="y", labelsize=7)

    unc = tables["uncertainty_stage_summary"]
    top_unc = unc.sort_values("uncertainty_score", ascending=False).head(5)
    ax6 = fig.add_axes([0.74, 0.30, 0.22, 0.20])
    bar_chart(ax6, [short_stage(s) for s in top_unc.journey_stage], top_unc.uncertainty_score.tolist(), "Uncertainty Stages", color=RED, fmt="{:.2f}")
    ax6.tick_params(axis="y", labelsize=7)

    hv = tables["hypothesis_visual_summary"]
    supported = hv[hv.evidence_grade.isin(["SUPPORTED", "WEAK"])].sort_values("absolute_difference", key=abs, ascending=False).head(5)
    ax7 = fig.add_axes([0.06, 0.06, 0.40, 0.18])
    bar_chart(ax7, [m[:20] for m in supported.mechanism_name.tolist()], (supported.absolute_difference.abs() * 100).tolist(),
              "Top Supported Behavioral Findings (|pt diff|)", color=GREEN, fmt="{:.0f}pts")
    ax7.tick_params(axis="y", labelsize=7)

    top_priority = bpi_detail.head(5)
    ax8 = fig.add_axes([0.56, 0.06, 0.40, 0.18])
    bar_chart(ax8, [m[:20] for m in top_priority.mechanism_name.tolist()], top_priority.bpi_mvp_score.tolist(),
              "Top Intervention Opportunities (BPI)", color=GOLD, fmt="{:.2f}")
    ax8.tick_params(axis="y", labelsize=7)

    footer(fig, "ABIDS Demonstration -- Page 1 of 1")
    pdf.savefig(fig); plt.close(fig)

print("executive dashboard built")
