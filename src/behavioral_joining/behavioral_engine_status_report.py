"""behavioral_engine_status_report.py -- overall status across the whole engine."""
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports" / "behavioral_joining"


def write_status_report(evidence_candidates, evidence_review, mapping_candidates, mapping_review,
                         lib_result, db_counts, out_dir: Path = REPORTS_DIR) -> Path:
    lines = []
    lines.append("# Aaryatech Behavioral Joining Intelligence -- Engine Status")
    lines.append(f"\nGenerated: {datetime.now(timezone.utc).isoformat()}")

    lines.append("\n## Scientific chain position")
    lines.append("```")
    lines.append("CANDIDATE JOURNEY               [done -- Task 1]")
    lines.append("  -> BEHAVIORAL EVIDENCE         [done -- proposed, pending human review]")
    lines.append("  -> HUMAN VALIDATION            [NOT DONE -- waiting on you]")
    lines.append("  -> BEHAVIORAL MECHANISM MAPPING[engine built, blocked -- no mechanism library]")
    lines.append("  -> HUMAN VALIDATION            [not started]")
    lines.append("  -> BEHAVIORAL HYPOTHESIS       [engine built, 0 generated -- needs approved mappings]")
    lines.append("  -> STATISTICAL TESTING         [module built, not run]")
    lines.append("  -> BEHAVIORAL FINDING          [none exist yet]")
    lines.append("```")

    lines.append("\n## Task 2 -- Behavioral Evidence Extraction")
    lines.append(f"- Status: **complete**")
    lines.append(f"- Evidence candidates: {len(evidence_candidates)}")
    lines.append(f"- Categories used: {evidence_candidates.evidence_category.nunique()}")
    lines.append(f"- Review file created: {len(evidence_review)} rows, all 'pending'")
    n_reviewed = (evidence_review.review_decision != "pending").sum() if len(evidence_review) else 0
    lines.append(f"- Items reviewed so far: {n_reviewed} (expected: 0, nobody has reviewed yet)")

    lines.append("\n## Task 3 -- Behavioral Mechanism Mapping")
    lines.append(f"- Engine status: **built and functional**")
    lines.append(f"- Mechanism library status: **{lib_result.status}**")
    if lib_result.status != "LOADED":
        lines.append("- **BLOCKED**: behavioral_mechanisms.json does not exist in this repository. "
                     "No replacement was fabricated. See mechanism_mapping_report.md for the full "
                     "list of paths checked.")
    lines.append(f"- Mapping candidates produced: {len(mapping_candidates)}")

    lines.append("\n## Task 4 -- Hypothesis Engine")
    lines.append("- Engine status: **built** (src/behavioral_joining/hypothesis_engine.py)")
    lines.append("- Hypotheses generated: 0 (correct -- requires approved mechanism mappings, "
                 "which don't exist yet because Task 3 is blocked on the mechanism library)")
    lines.append("- A single ILLUSTRATIVE example (not a real hypothesis, not saved anywhere) is "
                 "available via `hypothesis_engine.demo_hypothesis_illustration()` to show the "
                 "output shape.")

    lines.append("\n## Task 5 -- Statistical Testing Engine (foundation)")
    lines.append("- Module status: **built** (src/behavioral_joining/statistical_engine.py)")
    lines.append("- Functions available: chi_square_test, fishers_exact_test, t_test, mann_whitney_u, "
                 "compare_proportions, proportion_confidence_interval, "
                 "logistic_regression_confounder_check, benjamini_hochberg_adjustment, grade_evidence, "
                 "choose_test")
    lines.append("- held_out_test protection: `run_held_out_validation()` requires explicit "
                 "`authorized=True` + a non-empty `authorization_token` passed directly by a human; "
                 "no code in this project calls it. Verified by automated test.")
    lines.append("- No statistical test has been run against real hypotheses yet -- there are no "
                 "approved hypotheses to test.")

    lines.append("\n## Database")
    lines.append(f"- Path: database/behavioral_joining.db (separate file from the existing engine's database)")
    lines.append("- Row counts:")
    for t, c in db_counts.items():
        lines.append(f"  - {t}: {c}")

    lines.append("\n## Protected data -- confirmation")
    lines.append("- held_out_test rows were not inspected for outcome content anywhere in this run.")
    lines.append("- final_disposition, disposition_date, actual_start_date were stripped before "
                 "evidence extraction ran (outcome-blindness safeguard, automatically tested).")
    lines.append("- 08_scenario_ground_truth.csv was not loaded (hard-blocked at the data-loader level).")

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "behavioral_engine_status.md"
    out_path.write_text("\n".join(lines))
    return out_path
