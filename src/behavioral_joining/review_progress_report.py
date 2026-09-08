"""review_progress_report.py -- regenerates human_review_progress.md every time
the review tool runs (or is called directly)."""
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports" / "behavioral_joining"


def write_human_review_progress_report(review_df: pd.DataFrame, out_dir: Path = REPORTS_DIR) -> Path:
    total = len(review_df)
    counts = review_df.human_decision.value_counts()
    pending = int(counts.get("PENDING", 0))
    approved = int(counts.get("APPROVE", 0))
    edited = int(counts.get("EDIT", 0))
    rejected = int(counts.get("REJECT", 0))
    completed = approved + edited + rejected
    pct = (completed / total * 100) if total else 0.0

    lines = []
    lines.append("# Human Review Progress")
    lines.append(f"\nGenerated: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"\n- Total review sample: {total}")
    lines.append(f"- Pending: {pending}")
    lines.append(f"- Approved: {approved}")
    lines.append(f"- Edited: {edited}")
    lines.append(f"- Rejected: {rejected}")
    lines.append(f"- Completion: {pct:.1f}%")

    lines.append("\n## By evidence category")
    for cat, sub in review_df.groupby("evidence_category"):
        c = sub.human_decision.value_counts()
        lines.append(f"- {cat}: total={len(sub)}, pending={c.get('PENDING',0)}, "
                     f"approved={c.get('APPROVE',0)}, edited={c.get('EDIT',0)}, "
                     f"rejected={c.get('REJECT',0)}")

    lines.append("\n## By information quality")
    for q, sub in review_df.groupby("information_quality"):
        c = sub.human_decision.value_counts()
        lines.append(f"- {q}: total={len(sub)}, pending={c.get('PENDING',0)}, "
                     f"approved={c.get('APPROVE',0)}, edited={c.get('EDIT',0)}, "
                     f"rejected={c.get('REJECT',0)}")

    lines.append("\n## By duplication status")
    for d, sub in review_df.groupby("duplication_status"):
        c = sub.human_decision.value_counts()
        lines.append(f"- {d}: total={len(sub)}, pending={c.get('PENDING',0)}, "
                     f"approved={c.get('APPROVE',0)}, edited={c.get('EDIT',0)}, "
                     f"rejected={c.get('REJECT',0)}")

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "human_review_progress.md"
    out_path.write_text("\n".join(lines))
    return out_path
