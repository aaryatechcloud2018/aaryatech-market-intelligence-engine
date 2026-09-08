"""
generate_validation_report.py

Runs schema + logical validation and produces a concise Markdown report under
reports/behavioral_joining/. Also validates that held_out_test rows exist and are
structurally sound WITHOUT analyzing their outcome distribution for pattern-discovery
purposes (that would violate the research-split safeguard).
"""
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

from .data_loader import load_dataset, RAW_DIR
from .schema_validation import validate_files_exist, validate_schema
from .logical_validation import validate_logic

REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports" / "behavioral_joining"


def _fmt_counts(series: pd.Series, total: int = None) -> str:
    lines = []
    total = total if total is not None else series.sum()
    for k, v in series.items():
        lines.append(f"- {k}: {v} ({v/total:.1%})")
    return "\n".join(lines)


def generate_report(raw_dir: Path = RAW_DIR, out_dir: Path = REPORTS_DIR) -> Path:
    file_check = validate_files_exist(raw_dir)
    ds = load_dataset(raw_dir)
    schema_result = validate_schema(ds)
    logic_result = validate_logic(ds)

    apps = ds.applications
    comms = ds.communications
    stages = ds.stage_events

    # Structural-only check on held_out_test: confirm it exists and has the right
    # shape/columns. Deliberately NOT summarizing final_disposition *within* this
    # split beyond a raw row count -- that is left untouched per the research-split
    # safeguard until formal hypothesis testing.
    held_out = apps[apps.research_split == "held_out_test"]
    held_out_structural_ok = (
        len(held_out) > 0
        and held_out.application_id.is_unique
        and held_out.application_id.notna().all()
    )

    missing_summary = apps.isna().mean().sort_values(ascending=False)
    missing_summary = missing_summary[missing_summary > 0]

    dup_summary_lines = []
    for name, pk in [("applications", "application_id"), ("communications", "log_id"),
                      ("stage_events", "event_id"), ("clients", "client_account_id"),
                      ("recruiters", "recruiter_id"), ("requisitions", "requisition_id")]:
        df = getattr(ds, name)
        dup_summary_lines.append(f"- {name}.{pk}: {df[pk].duplicated().sum()} duplicates")

    lines = []
    lines.append("# Behavioral Joining Intelligence -- Data Foundation Validation Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")
    lines.append("**Scope:** data foundation only. No behavioral analysis, mechanism mapping, "
                  "hypothesis generation, statistical testing, or scoring was performed to "
                  "produce this report.")
    lines.append("")

    lines.append("## 1. Dataset Dimensions")
    lines.append(f"- Total applications: {len(apps)}")
    lines.append(f"- Unique candidates: {apps.candidate_id.nunique()}")
    lines.append(f"- Total communications: {len(comms)}")
    lines.append(f"- Total stage events: {len(stages)}")
    lines.append(f"- Clients: {len(ds.clients)}")
    lines.append(f"- Recruiters: {len(ds.recruiters)}")
    lines.append(f"- Requisitions: {len(ds.requisitions)}")
    lines.append("")

    lines.append("## 2. Outcome Counts (final_disposition)")
    lines.append(_fmt_counts(apps.final_disposition.value_counts()))
    lines.append("")

    lines.append("## 3. Research Split Counts")
    lines.append(_fmt_counts(apps.research_split.value_counts()))
    lines.append(f"\n**held_out_test structural check:** "
                  f"{'PASSED' if held_out_structural_ok else 'FAILED'} "
                  f"({len(held_out)} rows, unique non-null application_id). "
                  "Outcome distribution within this split was NOT examined, per the "
                  "research-split safeguard.")
    lines.append("")

    lines.append("## 4. Job Family Counts")
    lines.append(_fmt_counts(apps.job_family.value_counts()))
    lines.append("")

    lines.append("## 5. Client Counts")
    lines.append(_fmt_counts(apps.client_account_id.value_counts()))
    lines.append("")

    lines.append("## 6. Recruiter Counts (top 5 / bottom 5 by volume)")
    rc = apps.recruiter_id.value_counts()
    lines.append("Top 5:")
    lines.append(_fmt_counts(rc.head(5), total=len(apps)))
    lines.append("\nBottom 5:")
    lines.append(_fmt_counts(rc.tail(5), total=len(apps)))
    lines.append("")

    lines.append("## 7. Missing-Value Summary (applications table)")
    if len(missing_summary):
        for col, pct in missing_summary.items():
            note = ""
            if col == "actual_start_date":
                note = " (expected -- only populated for joined_on_time/joined_late)"
            if col == "pay_rate_prior":
                note = " (expected -- not always disclosed by candidates)"
            lines.append(f"- {col}: {pct:.1%}{note}")
    else:
        lines.append("No missing values found.")
    lines.append("")

    lines.append("## 8. Duplicate ID Summary")
    lines.extend(dup_summary_lines)
    lines.append("")

    lines.append("## 9. File Existence Check")
    lines.append(file_check.summary().replace("\n", "\n\n"))
    lines.append("")

    lines.append("## 10. Schema Validation")
    lines.append(schema_result.summary().replace("\n", "\n\n"))
    lines.append("")

    lines.append("## 11. Logical Consistency Validation")
    lines.append(logic_result.summary().replace("\n", "\n\n"))
    lines.append("")

    lines.append("## 12. Derived Variable Sanity Checks")
    from .build_journey_master import build_master
    master = build_master(raw_dir)
    derived_cols = ["days_application_to_interview", "days_interview_to_offer",
                     "days_offer_to_response", "days_acceptance_to_expected_start",
                     "days_expected_to_actual_start", "pay_change_absolute",
                     "pay_change_percentage", "total_communications", "total_stage_events"]
    for col in derived_cols:
        s = master[col]
        lines.append(f"- {col}: min={s.min():.2f}, max={s.max():.2f}, "
                      f"mean={s.mean():.2f}, missing={s.isna().mean():.1%}")
    neg_check = master.days_application_to_interview.lt(0).sum() + \
                master.days_interview_to_offer.lt(0).sum() + \
                master.days_offer_to_response.lt(0).sum() + \
                master.days_acceptance_to_expected_start.lt(0).sum()
    lines.append(f"- Negative-duration violations across the four always-positive interval "
                 f"fields: {neg_check} (expect 0)")
    lines.append(f"- candidate_journey_master.csv shape: {master.shape[0]} rows x {master.shape[1]} columns")
    lines.append("")

    forbidden_terms = ["risk_score", "probability", "prediction", "mechanism",
                        "behavioral_", "bias_", "psych"]
    leaked = [c for c in master.columns if any(t in c.lower() for t in forbidden_terms)]
    lines.append(f"- Forbidden-column safeguard: {'FAILED - found ' + str(leaked) if leaked else 'PASSED (no risk/prediction/mechanism columns present)'}")
    lines.append("")

    overall_pass = (file_check.passed and schema_result.passed and logic_result.passed
                     and held_out_structural_ok and not leaked)
    lines.append(f"## Overall Result: {'PASSED' if overall_pass else 'FAILED -- see errors above'}")
    lines.append("")
    lines.append("08_scenario_ground_truth.csv was NOT loaded, read, or referenced anywhere "
                  "in this validation run.")

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "validation_report.md"
    out_path.write_text("\n".join(lines))
    return out_path, overall_pass


if __name__ == "__main__":
    path, ok = generate_report()
    print(f"Validation report written: {path}")
    print(f"Overall result: {'PASSED' if ok else 'FAILED'}")
