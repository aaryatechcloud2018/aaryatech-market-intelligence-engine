"""
calibration_metrics.py

HUMAN-REVIEW AGREEMENT METRICS -- not "model accuracy". There is no independently
labeled ground-truth evaluation set here, so nothing in this module may be called
an accuracy figure. These are simply rates describing how often a human reviewer
agreed with, changed, or dismissed the AI's proposals.
"""
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports" / "behavioral_joining"


def compute_evidence_agreement_metrics(review_df: pd.DataFrame) -> dict:
    reviewed = review_df[review_df.human_decision.isin(["APPROVE", "EDIT", "REJECT"])]
    n_reviewed = len(reviewed)
    if n_reviewed == 0:
        return {"status": "no_reviews_yet", "n_reviewed": 0}

    counts = reviewed.human_decision.value_counts()
    metrics = {
        "status": "computed",
        "n_reviewed": n_reviewed,
        "n_total_sample": len(review_df),
        "approval_rate": counts.get("APPROVE", 0) / n_reviewed,
        "edit_rate": counts.get("EDIT", 0) / n_reviewed,
        "rejection_rate": counts.get("REJECT", 0) / n_reviewed,
        # "category agreement" = approved unchanged / (approved + edited) -- edits
        # that changed the category are treated as disagreement with the original
        # category; edits that only changed description/notes are not distinguishable
        # here from the CSV alone, so this is a conservative (lower-bound) figure.
        "category_agreement_rate": None,
    }

    approved_or_edited = reviewed[reviewed.human_decision.isin(["APPROVE", "EDIT"])]
    if len(approved_or_edited):
        unchanged_category = (
            approved_or_edited.human_evidence_category == approved_or_edited.evidence_category
        )
        metrics["category_agreement_rate"] = unchanged_category.mean()

    by_category = {}
    for cat, sub in reviewed.groupby("evidence_category"):
        c = sub.human_decision.value_counts()
        n = len(sub)
        by_category[cat] = {
            "n_reviewed": n,
            "approval_rate": c.get("APPROVE", 0) / n,
            "edit_rate": c.get("EDIT", 0) / n,
            "rejection_rate": c.get("REJECT", 0) / n,
        }
    metrics["agreement_by_category"] = by_category

    by_confidence = {}
    reviewed = reviewed.copy()
    reviewed["confidence_band"] = reviewed.extractor_confidence.apply(
        lambda c: "high" if c >= 0.65 else ("medium" if c >= 0.5 else "low")
    )
    for band, sub in reviewed.groupby("confidence_band"):
        c = sub.human_decision.value_counts()
        n = len(sub)
        by_confidence[band] = {
            "n_reviewed": n,
            "approval_rate": c.get("APPROVE", 0) / n,
            "edit_rate": c.get("EDIT", 0) / n,
            "rejection_rate": c.get("REJECT", 0) / n,
        }
    metrics["agreement_by_confidence_level"] = by_confidence

    by_quality = {}
    for q, sub in reviewed.groupby("information_quality"):
        c = sub.human_decision.value_counts()
        n = len(sub)
        by_quality[q] = {
            "n_reviewed": n,
            "approval_rate": c.get("APPROVE", 0) / n,
            "edit_rate": c.get("EDIT", 0) / n,
            "rejection_rate": c.get("REJECT", 0) / n,
        }
    metrics["agreement_by_information_quality"] = by_quality

    repeated_mask = reviewed.duplication_status.isin(
        ["repeated_but_usable", "likely_template", "same_application_duplicate", "potential_redundancy"]
    )
    for label, sub in [("repeated", reviewed[repeated_mask]), ("unique", reviewed[~repeated_mask])]:
        if len(sub) == 0:
            continue
        c = sub.human_decision.value_counts()
        n = len(sub)
        metrics.setdefault("agreement_repeated_vs_unique", {})[label] = {
            "n_reviewed": n,
            "approval_rate": c.get("APPROVE", 0) / n,
            "edit_rate": c.get("EDIT", 0) / n,
            "rejection_rate": c.get("REJECT", 0) / n,
        }

    return metrics


def compute_mechanism_agreement_metrics(mapping_review_df: pd.DataFrame) -> dict:
    """For mechanism mapping -- computed once mapping review has actually happened."""
    reviewed = mapping_review_df[mapping_review_df.human_mapping_decision.isin(["APPROVE", "EDIT", "REJECT"])]
    n_reviewed = len(reviewed)
    if n_reviewed == 0:
        return {"status": "no_reviews_yet", "n_reviewed": 0}

    counts = reviewed.human_mapping_decision.value_counts()
    no_mech_confirmed = reviewed[
        (reviewed.mapping_status == "NO_SUPPORTED_MECHANISM") & (reviewed.human_mapping_decision == "APPROVE")
    ]
    metrics = {
        "status": "computed",
        "n_reviewed": n_reviewed,
        "mechanism_approval_rate": counts.get("APPROVE", 0) / n_reviewed,
        "mechanism_edit_rate": counts.get("EDIT", 0) / n_reviewed,
        "mechanism_rejection_rate": counts.get("REJECT", 0) / n_reviewed,
        "no_mechanism_confirmation_rate": len(no_mech_confirmed) / n_reviewed,
    }
    by_mechanism = {}
    for mech, sub in reviewed[reviewed.mechanism_id.astype(str).str.len() > 0].groupby("mechanism_id"):
        c = sub.human_mapping_decision.value_counts()
        n = len(sub)
        by_mechanism[mech] = {"n_reviewed": n, "approval_rate": c.get("APPROVE", 0) / n}
    metrics["agreement_by_mechanism"] = by_mechanism
    return metrics


def write_calibration_report(evidence_metrics: dict, mechanism_metrics: dict,
                              out_dir: Path = REPORTS_DIR) -> Path:
    lines = []
    lines.append("# Human-Review Agreement Metrics")
    lines.append(f"\nGenerated: {datetime.now(timezone.utc).isoformat()}")
    lines.append("\n**These are human-review agreement metrics, not model accuracy.** There is no "
                 "independently labeled evaluation set behind these numbers -- they describe how "
                 "often a human reviewer agreed with, changed, or dismissed the AI's proposals, "
                 "nothing more.")

    lines.append("\n## Evidence extraction")
    if evidence_metrics["status"] == "no_reviews_yet":
        lines.append("No evidence has been reviewed yet -- WAITING FOR HUMAN REVIEW.")
    else:
        lines.append(f"- Reviewed: {evidence_metrics['n_reviewed']} of {evidence_metrics['n_total_sample']}")
        lines.append(f"- Approval rate: {evidence_metrics['approval_rate']:.1%}")
        lines.append(f"- Edit rate: {evidence_metrics['edit_rate']:.1%}")
        lines.append(f"- Rejection rate: {evidence_metrics['rejection_rate']:.1%}")
        if evidence_metrics.get("category_agreement_rate") is not None:
            lines.append(f"- Category agreement rate (approved/edited items whose category was "
                         f"NOT changed by the human): {evidence_metrics['category_agreement_rate']:.1%}")

        lines.append("\n### Agreement by evidence category")
        for cat, m in evidence_metrics.get("agreement_by_category", {}).items():
            lines.append(f"- {cat}: n={m['n_reviewed']}, approve={m['approval_rate']:.0%}, "
                         f"edit={m['edit_rate']:.0%}, reject={m['rejection_rate']:.0%}")

        lines.append("\n### Agreement by extractor confidence level")
        for band, m in evidence_metrics.get("agreement_by_confidence_level", {}).items():
            lines.append(f"- {band}: n={m['n_reviewed']}, approve={m['approval_rate']:.0%}, "
                         f"edit={m['edit_rate']:.0%}, reject={m['rejection_rate']:.0%}")

        lines.append("\n### Agreement by information quality")
        for q, m in evidence_metrics.get("agreement_by_information_quality", {}).items():
            lines.append(f"- {q}: n={m['n_reviewed']}, approve={m['approval_rate']:.0%}, "
                         f"edit={m['edit_rate']:.0%}, reject={m['rejection_rate']:.0%}")

        lines.append("\n### Agreement: repeated vs. unique text")
        for label, m in evidence_metrics.get("agreement_repeated_vs_unique", {}).items():
            lines.append(f"- {label}: n={m['n_reviewed']}, approve={m['approval_rate']:.0%}, "
                         f"edit={m['edit_rate']:.0%}, reject={m['rejection_rate']:.0%}")

    lines.append("\n## Mechanism mapping")
    if mechanism_metrics["status"] == "no_reviews_yet":
        lines.append("No mechanism mappings have been reviewed yet -- WAITING FOR HUMAN REVIEW.")
    else:
        lines.append(f"- Reviewed: {mechanism_metrics['n_reviewed']}")
        lines.append(f"- Mechanism approval rate: {mechanism_metrics['mechanism_approval_rate']:.1%}")
        lines.append(f"- Mechanism edit rate: {mechanism_metrics['mechanism_edit_rate']:.1%}")
        lines.append(f"- Mechanism rejection rate: {mechanism_metrics['mechanism_rejection_rate']:.1%}")
        lines.append(f"- No-mechanism confirmation rate: {mechanism_metrics['no_mechanism_confirmation_rate']:.1%}")
        lines.append("\n### Agreement by mechanism")
        for mech, m in mechanism_metrics.get("agreement_by_mechanism", {}).items():
            lines.append(f"- {mech}: n={m['n_reviewed']}, approve={m['approval_rate']:.0%}")

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "calibration_report.md"
    out_path.write_text("\n".join(lines))
    return out_path
