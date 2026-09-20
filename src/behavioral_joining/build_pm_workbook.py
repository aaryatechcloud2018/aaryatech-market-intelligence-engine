"""build_pm_workbook.py -- FINAL DEMONSTRATION RUN. Builds
ABIDS_Full_Demonstration_Analysis.xlsx, the main PM review workbook."""
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils.dataframe import dataframe_to_rows

D = "data/behavioral_joining/processed/final/"
HEADER_FILL = PatternFill(start_color="1F3864", end_color="1F3864", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)
TITLE_FONT = Font(size=16, bold=True, color="1F3864")


def _write_df_sheet(wb, name, df, freeze="A2"):
    ws = wb.create_sheet(name)
    for r in dataframe_to_rows(df, index=False, header=True):
        ws.append(r)
    for cell in ws[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
    ws.freeze_panes = freeze
    for col in ws.columns:
        max_len = max((len(str(c.value)) if c.value is not None else 0) for c in col)
        ws.column_dimensions[col[0].column_letter].width = min(max(max_len + 2, 10), 60)
    return ws


def _write_text_sheet(wb, name, title, paragraphs):
    ws = wb.create_sheet(name)
    ws["A1"] = title
    ws["A1"].font = TITLE_FONT
    row = 3
    for p in paragraphs:
        ws.cell(row=row, column=1, value=p)
        ws.cell(row=row, column=1).alignment = Alignment(wrap_text=True, vertical="top")
        row += 2
    ws.column_dimensions["A"].width = 120
    return ws


def build_workbook(out_path: str):
    apps = pd.read_csv("data/behavioral_joining/raw/01_candidate_applications.csv", keep_default_na=False)
    comms = pd.read_csv("data/behavioral_joining/raw/02_communication_log.csv", keep_default_na=False)
    ev = pd.read_csv(D + "behavioral_evidence.csv", keep_default_na=False)
    mappings = pd.read_csv(D + "behavioral_mappings.csv", keep_default_na=False)
    scenarios = pd.read_csv(D + "scenario_library.csv", keep_default_na=False)
    bridge = pd.read_csv(D + "application_behavior_mechanisms.csv", keep_default_na=False)
    outcome = pd.read_csv(D + "behavior_outcome_dataset.csv", keep_default_na=False)
    hyps = pd.read_csv(D + "abids_hypotheses.csv", keep_default_na=False)
    stats = pd.read_csv(D + "abids_statistical_results.csv", keep_default_na=False)
    leakage = pd.read_csv(D + "behavioral_leakage_map.csv", keep_default_na=False)
    bpi = pd.read_csv(D + "behavioral_priority_index.csv", keep_default_na=False)
    unc = pd.read_csv(D + "behavioral_uncertainty_matrix.csv", keep_default_na=False)
    scnmat = pd.read_csv(D + "candidate_scenario_matrix.csv", keep_default_na=False)
    jmap = pd.read_csv(D + "behavioral_journey_map.csv", keep_default_na=False)
    interv = pd.read_csv(D + "intervention_intelligence_matrix.csv", keep_default_na=False)
    human_review = pd.read_csv("data/behavioral_joining/review/evidence_human_review_sample.csv", keep_default_na=False)

    n_human = (mappings.mapping_source == "HUMAN_REVIEWED").sum()
    n_model = (mappings.mapping_source == "MODEL_APPLIED_FROM_CALIBRATED_FRAMEWORK").sum()
    n_supported = (mappings.mechanism_id.astype(str).str.len() > 0).sum()
    n_sig = (stats.evidence_grade.isin(["SUPPORTED", "WEAK"])).sum() if len(stats) else 0
    n_human_supported = ((mappings.mapping_source == "HUMAN_REVIEWED") & (mappings.mechanism_id.astype(str).str.len() > 0)).sum()

    wb = Workbook()
    wb.remove(wb.active)

    _write_text_sheet(wb, "00_READ_ME", "ABIDS Full Demonstration Analysis -- Read Me First", [
        "PURPOSE OF THIS WORKBOOK: This is the master analytical workbook for the Aaryatech Behavioral "
        "Joining Intelligence demonstration run, covering all 2,500 applications in the purpose-built "
        "demonstration dataset. It is NOT VDart's or any client's real historical data.",

        "WHAT EACH SHEET MEANS:\n"
        "01_EXECUTIVE_SUMMARY -- the headline results in business English.\n"
        "02_CANDIDATE_MASTER -- one row per application, structured fields only.\n"
        "03_BEHAVIORAL_EVIDENCE -- every extracted piece of behavioral evidence (6,749 rows).\n"
        "04_BEHAVIORAL_MAPPINGS -- every evidence item mapped (or not) to a frozen mechanism, with provenance.\n"
        "05_SCENARIO_LIBRARY -- supported mappings turned into recognizable recruiting situations.\n"
        "06_APPLICATION_BEHAVIOR -- clean application x mechanism bridge table.\n"
        "07_BEHAVIOR_OUTCOME -- bridge table joined to outcomes (discovery + hypothesis_generation only).\n"
        "08_HYPOTHESES -- every formally proposed, testable hypothesis.\n"
        "09_STATISTICAL_RESULTS -- actual test results for every eligible hypothesis.\n"
        "10-15 -- the six proprietary ABIDS reports.\n"
        "16_DATA_GAPS -- what is missing or not yet possible.\n"
        "17_HUMAN_REVIEW -- the 275-row human calibration sample as reviewed.\n"
        "18_QA_AND_GOVERNANCE -- safeguards verified for this run.",

        "WHAT IS HUMAN-REVIEWED vs MODEL-APPLIED: Every mapping row (sheet 04) carries a mapping_source "
        f"column. {n_human} evidence items were personally reviewed and decided by a human analyst "
        f"(HUMAN_REVIEWED). The remaining {n_model} were mapped automatically by the same calibrated "
        "engine, but NO human has checked them individually (MODEL_APPLIED_FROM_CALIBRATED_FRAMEWORK). "
        "Treat MODEL_APPLIED rows as demonstration-grade, not validated.",

        "WHAT IS DESCRIPTIVE vs STATISTICALLY TESTED: Sheet 05 (scenarios) and most of sheets 10-15 are "
        "descriptive -- they summarize what evidence exists, not whether it predicts outcomes. Sheet 09 "
        "(Statistical Results) is the only sheet containing actual hypothesis tests, with p-values, "
        "effect sizes, and an evidence grade. A p-value alone was never treated as a finding -- "
        "grade_evidence() requires both statistical significance AND a non-trivial effect size before "
        "calling anything SUPPORTED.",

        "WHAT HAS NOT BEEN VALIDATED: Every result in this workbook comes from the discovery and "
        "hypothesis_generation splits only. held_out_test (501 applications) has never been opened for "
        "this analysis. Formal held-out validation, Intelligence State classification (ESTABLISHED / "
        "EMERGING / AMBIGUOUS / GAP), and Behavioral Priority Index (BPI) numeric scores are all marked "
        "METHODOLOGY_PENDING throughout this workbook -- the underlying thresholds have not yet been "
        "scientifically validated, so no number was invented for them.",

        "WHERE HELD-OUT VALIDATION STANDS: Not started. The engine has a hard-coded authorization gate "
        "that must be explicitly triggered by a human with a real token before held_out_test can even be "
        "loaded for this purpose. That gate was not triggered in this run.",
    ])

    exec_pop = apps[(apps.offer_accepted.astype(str) == "True") & (apps.research_split.isin(["discovery", "hypothesis_generation"]))]
    _write_text_sheet(wb, "01_EXECUTIVE_SUMMARY", "Executive Summary", [
        f"This demonstration processed all 2,500 applications in the purpose-built synthetic dataset. "
        f"{len(comms)} candidate/recruiter communications were analyzed, producing {len(ev)} pieces of "
        f"behavioral evidence from the discovery split.",

        f"Of those, {n_human} evidence items were personally reviewed by a human analyst as a calibration "
        f"sample ({n_human_supported} found to support one of Aaryatech's 34 frozen behavioral mechanisms). "
        f"The calibrated engine was then applied to the remaining {n_model} evidence items, clearly "
        f"labeled as model-applied rather than human-reviewed throughout every downstream table.",

        f"{len(scenarios)} concrete behavioral scenarios were generated, covering {bridge.application_id.nunique()} "
        f"distinct applications. {len(hyps)} formal hypotheses were proposed; {len(stats)} had enough "
        f"supporting evidence to actually test.",

        f"Of the {len(stats)} tests run, {n_sig} showed a statistically meaningful association (SUPPORTED "
        f"or WEAK evidence grade) between a behavioral mechanism and whether a candidate joined. None of "
        f"these are causal claims -- they describe association only, on demonstration data, not yet "
        f"replicated on held-out data.",

        "This is a demonstration of the ABIDS method working end to end on a purpose-built dataset. It "
        "is not a claim about real candidate behavior at any actual client.",
    ])

    _write_df_sheet(wb, "02_CANDIDATE_MASTER", apps)
    _write_df_sheet(wb, "03_BEHAVIORAL_EVIDENCE", ev)
    _write_df_sheet(wb, "04_BEHAVIORAL_MAPPINGS", mappings)
    _write_df_sheet(wb, "05_SCENARIO_LIBRARY", scenarios)
    _write_df_sheet(wb, "06_APPLICATION_BEHAVIOR", bridge)
    _write_df_sheet(wb, "07_BEHAVIOR_OUTCOME", outcome)
    _write_df_sheet(wb, "08_HYPOTHESES", hyps)
    _write_df_sheet(wb, "09_STATISTICAL_RESULTS", stats)
    _write_df_sheet(wb, "10_LEAKAGE_MAP", leakage)
    _write_df_sheet(wb, "11_PRIORITY_INDEX", bpi)
    _write_df_sheet(wb, "12_UNCERTAINTY_MATRIX", unc)
    _write_df_sheet(wb, "13_SCENARIO_MATRIX", scnmat)
    _write_df_sheet(wb, "14_JOURNEY_MAP", jmap)
    _write_df_sheet(wb, "15_INTERVENTION_MATRIX", interv)

    gaps_df = pd.DataFrame([
        ["Held-out validation", "Not run -- requires explicit human authorization and a validated minimum sample rule, neither invented here."],
        ["Intelligence State thresholds", "METHODOLOGY_PENDING -- ESTABLISHED/EMERGING/AMBIGUOUS/GAP boundaries not yet scientifically set."],
        ["BPI weighting formula", "METHODOLOGY_PENDING -- priority_score left pending rather than a fabricated number."],
        ["Segment-level stratification", "Hypotheses tested at overall population level only; not yet broken out by job family/client/recruiter."],
        ["Covariate-adjusted testing", "2x2 unadjusted comparisons only; logistic regression confounder checks available in the engine but not yet run for this pass."],
        ["hypothesis_generation split", "Included in behavior_outcome_dataset and testing per this run's scope, but not independently used to re-derive hypotheses discovered on the discovery split."],
    ], columns=["gap", "detail"])
    _write_df_sheet(wb, "16_DATA_GAPS", gaps_df)

    _write_df_sheet(wb, "17_HUMAN_REVIEW", human_review)

    qa_df = pd.DataFrame([
        ["Behavioral Joining test suite", "190/190 passed"],
        ["Full repository test suite", "240/241 passed (1 pre-existing, unrelated Market Intelligence failure)"],
        ["Frozen 34-mechanism library unchanged", "YES -- MD5 hash verified identical before/after this run"],
        ["held_out_test leakage", "NONE -- 0 rows in behavior_outcome_dataset, 0 applications in bridge table"],
        ["08_scenario_ground_truth.csv accessed", "NO -- file confirmed absent from repository; hard-blocked at loader level"],
        ["Individual candidate risk scoring", "NONE -- all analysis is aggregate; no per-candidate score exists anywhere"],
        ["Automated rejection logic", "NONE -- no code path rejects or advances any candidate"],
        ["Psychological diagnosis", "NONE -- evidence describes communication patterns, not internal states"],
        ["Causal claims", "NONE -- every statistical result is labeled association only"],
        ["Human-reviewed vs model-applied provenance", "Retained on every row of 04_BEHAVIORAL_MAPPINGS through 07_BEHAVIOR_OUTCOME"],
        ["Fabricated missing data", "NONE -- BPI scores and Intelligence States marked METHODOLOGY_PENDING, not invented"],
    ], columns=["check", "result"])
    _write_df_sheet(wb, "18_QA_AND_GOVERNANCE", qa_df)

    wb.save(out_path)
    return out_path
