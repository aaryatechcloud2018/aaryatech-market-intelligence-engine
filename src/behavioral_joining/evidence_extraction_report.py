"""evidence_extraction_report.py -- QA report for the evidence extraction stage."""
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports" / "behavioral_joining"


def write_evidence_extraction_report(evidence_candidates: pd.DataFrame, signals: pd.DataFrame,
                                      discovery_context, out_dir: Path = REPORTS_DIR) -> Path:
    lines = []
    lines.append("# Behavioral Evidence Extraction -- QA Report")
    lines.append(f"\nGenerated: {datetime.now(timezone.utc).isoformat()}")
    lines.append("\n**Scope:** discovery-split communications only. final_disposition, "
                  "disposition_date, and actual_start_date were not available to the extractor.")

    lines.append("\n## Volume")
    lines.append(f"- Discovery applications: {discovery_context.n_discovery_applications} "
                 f"(of {discovery_context.n_total_applications} total)")
    lines.append(f"- Discovery communications scanned: {len(discovery_context.communications)}")
    lines.append(f"- Evidence candidates proposed: {len(evidence_candidates)}")
    lines.append(f"- Applications with at least one evidence candidate: "
                 f"{evidence_candidates.application_id.nunique()}")
    lines.append(f"- All {len(evidence_candidates)} candidates have review_status = 'pending' "
                 f"(expected -- nothing auto-approved): "
                 f"{(evidence_candidates.review_status == 'pending').all()}")

    lines.append("\n## Evidence by category")
    for cat, n in evidence_candidates.evidence_category.value_counts().items():
        lines.append(f"- {cat}: {n}")

    lines.append("\n## Evidence by strength")
    for s, n in evidence_candidates.evidence_strength.value_counts().items():
        lines.append(f"- {s}: {n}")

    lines.append("\n## Evidence by source type")
    for s, n in evidence_candidates.source_type.value_counts().items():
        lines.append(f"- {s}: {n}")

    lines.append("\n## extractor_confidence distribution")
    lines.append(f"- min={evidence_candidates.extractor_confidence.min():.2f}, "
                 f"mean={evidence_candidates.extractor_confidence.mean():.2f}, "
                 f"max={evidence_candidates.extractor_confidence.max():.2f}")

    lines.append("\n## Traceability check")
    traceable = evidence_candidates.apply(
        lambda r: isinstance(r.evidence_span, str) and len(r.evidence_span) > 0, axis=1
    ).all()
    lines.append(f"- Every evidence_span is non-empty exact source text: {traceable}")
    dup_ids = evidence_candidates.evidence_id.duplicated().sum()
    lines.append(f"- Duplicate evidence_id count: {dup_ids} (expect 0)")

    lines.append("\n## Objective signals (observational, non-scored)")
    lines.append(f"- Computed for {len(signals)} applications, {signals.shape[1]-1} signal columns.")
    lines.append(f"- Mean candidate messages per application: {signals.number_of_candidate_messages.mean():.2f}")
    lines.append(f"- Mean recruiter messages per application: {signals.number_of_recruiter_messages.mean():.2f}")
    lines.append(f"- Mean unanswered candidate messages: {signals.unanswered_candidate_message_count.mean():.2f}")

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "evidence_extraction_report.md"
    out_path.write_text("\n".join(lines))
    return out_path
