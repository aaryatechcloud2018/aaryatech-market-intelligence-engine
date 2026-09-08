"""
hypothesis_readiness.py

Identifies which mechanisms MAY be ready for formal hypothesis generation, based on
how much human-APPROVED/EDITED mechanism-mapping evidence currently supports them.

MVP CONFIGURATION -- NOT SCIENTIFICALLY VALIDATED THRESHOLDS.

The numbers in READINESS_CONFIG below are conservative development defaults chosen
to keep the MVP moving, not a scientific determination of what counts as "enough"
evidence for a real behavioral finding. An analyst/behavioral scientist should
review and likely tighten these before any hypothesis generated under them is
treated as meaningful.
"""
from pathlib import Path
import pandas as pd

READINESS_CONFIG = {
    "_label": "MVP CONFIGURATION -- NOT SCIENTIFICALLY VALIDATED THRESHOLDS",
    "minimum_approved_evidence_count": 5,
    "minimum_unique_applications": 3,
    "minimum_mapping_confidence": 0.4,
    "maximum_single_template_share": 0.5,  # no more than 50% of supporting evidence
                                            # may come from a single duplicated/templated span
}

READINESS_COLUMNS = [
    "mechanism_id", "mechanism_name", "approved_mapping_count", "unique_application_count",
    "unique_evidence_span_count", "template_share", "high_confidence_count",
    "medium_confidence_count", "ready_for_hypothesis_generation", "readiness_reason",
]


def _confidence_band(c):
    if c >= 0.65:
        return "high"
    if c >= 0.5:
        return "medium"
    return "low"


def compute_hypothesis_readiness(mapping_review_df: pd.DataFrame,
                                  evidence_quality_df: pd.DataFrame = None,
                                  config: dict = None) -> pd.DataFrame:
    """
    mapping_review_df: mechanism_human_review.csv contents. Only rows with
        human_mapping_decision in [APPROVE, EDIT] AND a non-empty selected mechanism
        count as supporting evidence for that mechanism.
    evidence_quality_df: optional, used to compute template_share (falls back to 0
        for all rows if not supplied, since without it we cannot detect templates).
    """
    cfg = config or READINESS_CONFIG

    approved = mapping_review_df[
        mapping_review_df.human_mapping_decision.isin(["APPROVE", "EDIT"])
    ].copy()
    approved["effective_mechanism_id"] = approved["human_selected_mechanism"].where(
        approved["human_selected_mechanism"].astype(str).str.len() > 0, approved["mechanism_id"]
    )
    approved = approved[approved.effective_mechanism_id.astype(str).str.len() > 0]

    if len(approved) == 0:
        return pd.DataFrame(columns=READINESS_COLUMNS)

    rows = []
    for mech_id, sub in approved.groupby("effective_mechanism_id"):
        mech_name = sub.mechanism_name.iloc[0] if "mechanism_name" in sub.columns else ""
        n_mappings = len(sub)
        n_apps = sub.application_id.nunique()
        n_spans = sub.evidence_id.nunique()

        template_share = 0.0
        if evidence_quality_df is not None and "evidence_id" in evidence_quality_df.columns:
            q = sub.merge(evidence_quality_df[["evidence_id", "is_high_frequency_template"]],
                           on="evidence_id", how="left")
            template_share = q["is_high_frequency_template"].fillna(False).mean()

        conf_col = "mapping_confidence" if "mapping_confidence" in sub.columns else None
        high_conf = int((sub[conf_col].apply(_confidence_band) == "high").sum()) if conf_col else 0
        med_conf = int((sub[conf_col].apply(_confidence_band) == "medium").sum()) if conf_col else 0

        reasons = []
        ready = True
        if n_mappings < cfg["minimum_approved_evidence_count"]:
            ready = False
            reasons.append(f"only {n_mappings} approved/edited mappings "
                           f"(need >= {cfg['minimum_approved_evidence_count']})")
        if n_apps < cfg["minimum_unique_applications"]:
            ready = False
            reasons.append(f"only {n_apps} unique applications "
                           f"(need >= {cfg['minimum_unique_applications']})")
        if template_share > cfg["maximum_single_template_share"]:
            ready = False
            reasons.append(f"template share {template_share:.0%} exceeds max "
                           f"{cfg['maximum_single_template_share']:.0%}")
        if not reasons:
            reasons.append("meets all MVP development thresholds (not a scientific determination)")

        rows.append({
            "mechanism_id": mech_id,
            "mechanism_name": mech_name,
            "approved_mapping_count": n_mappings,
            "unique_application_count": n_apps,
            "unique_evidence_span_count": n_spans,
            "template_share": round(float(template_share), 3),
            "high_confidence_count": high_conf,
            "medium_confidence_count": med_conf,
            "ready_for_hypothesis_generation": ready,
            "readiness_reason": "; ".join(reasons),
        })

    return pd.DataFrame(rows, columns=READINESS_COLUMNS)
