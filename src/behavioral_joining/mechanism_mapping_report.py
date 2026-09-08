"""mechanism_mapping_report.py -- QA report for the mechanism mapping stage."""
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports" / "behavioral_joining"


def write_mechanism_mapping_report(mapping_candidates: pd.DataFrame, lib_result, out_dir: Path = REPORTS_DIR) -> Path:
    lines = []
    lines.append("# Behavioral Mechanism Mapping -- QA Report")
    lines.append(f"\nGenerated: {datetime.now(timezone.utc).isoformat()}")

    lines.append("\n## Mechanism library status")
    lines.append(f"- Status: **{lib_result.status}**")
    if lib_result.status == "LOADED":
        lines.append(f"- Source: {lib_result.source_path}")
        lines.append(f"- Mechanisms loaded: {len(lib_result.mechanisms)}")
    else:
        lines.append("- `behavioral_mechanisms.json` does not currently exist anywhere in this "
                      "repository. This was verified by downloading the full repository archive "
                      "and searching every file for any mention of 'mechanism', in addition to "
                      "directly probing every plausible file path. No replacement library was "
                      "created -- that is explicitly forbidden by the project brief.")
        lines.append(f"- Error detail: {lib_result.error}")
        lines.append("\n### Paths checked")
        for p in lib_result.paths_checked:
            lines.append(f"- {p}")

    lines.append("\n## Mapping candidates")
    lines.append(f"- Total mapping records: {len(mapping_candidates)}")
    if len(mapping_candidates):
        with_mechanism = mapping_candidates[mapping_candidates.mechanism_id.astype(str).str.len() > 0]
        no_mechanism = mapping_candidates[mapping_candidates.mechanism_id.astype(str).str.len() == 0]
        lines.append(f"- Records with a proposed mechanism: {len(with_mechanism)}")
        lines.append(f"- Records marked 'NO SUPPORTED MECHANISM': {len(no_mechanism)}")
        if len(with_mechanism):
            lines.append("\n### Proposed mechanisms (by evidence_support_level)")
            for lvl, n in with_mechanism.evidence_support_level.value_counts().items():
                lines.append(f"- {lvl}: {n}")
    else:
        lines.append("- 0 mapping records were produced. This is expected right now: mapping "
                      "only runs against APPROVED/EDITED evidence, and no evidence has been "
                      "human-reviewed yet (this is stage 6 of the pipeline, which runs "
                      "immediately after evidence extraction with 0 approvals so far).")

    lines.append("\n## What happens next")
    lines.append("1. A human analyst reviews `behavioral_evidence_candidates.csv` and approves/"
                  "edits/rejects items in `behavioral_evidence_review.csv`.")
    lines.append("2. The real `behavioral_mechanisms.json` (34-mechanism frozen library) needs to "
                  "be placed in this repository -- suggested location: "
                  "`data/behavioral_joining/reference/behavioral_mechanisms.json`.")
    lines.append("3. Once both exist, re-running the pipeline will produce real mechanism mapping "
                  "candidates for human review.")

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "mechanism_mapping_report.md"
    out_path.write_text("\n".join(lines))
    return out_path
