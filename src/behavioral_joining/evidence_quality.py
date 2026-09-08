"""
evidence_quality.py

Quality-control layer over raw behavioral evidence proposals, BEFORE anything goes
to human review. Never modifies behavioral_evidence_candidates.csv -- produces a
separate, enriched file that adds quality signal columns keyed by evidence_id.

Duplication is CLASSIFIED, not deleted. Repeated wording is common and legitimate in
real staffing communications (recruiters reuse boilerplate, candidates give short
generic replies) -- the goal is to flag what kind of repetition it is so the human
review sample (Task B) can deliberately include a healthy mix rather than either
drowning in near-identical rows or silently discarding real signal.
"""
import re
import pandas as pd

DUPLICATION_STATUSES = {
    "unique", "repeated_but_usable", "likely_template",
    "same_application_duplicate", "potential_redundancy",
}
INFORMATION_QUALITY_LEVELS = {"high", "medium", "low"}

# A span repeated across this many or more DISTINCT applications is treated as a
# high-frequency template (recruiter/system boilerplate), not a candidate-specific
# behavioral signal.
TEMPLATE_APPLICATION_THRESHOLD = 8
# A span repeated this many times in total (including within the same application)
# is a signal worth flagging even if it doesn't cross the template threshold.
REPEATED_MIN_COUNT = 2

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]")


def _normalize_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    t = text.lower().strip()
    t = _PUNCT_RE.sub("", t)
    t = _WS_RE.sub(" ", t)
    return t


def assess_evidence_quality(evidence_candidates: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a NEW DataFrame: evidence_id + quality columns, meant to be used
    alongside (joined to) the original candidates file -- never replacing it.
    """
    ev = evidence_candidates.copy()
    ev["_normalized_span"] = ev.evidence_span.apply(_normalize_text)

    # --- exact / normalized duplicate counts (global, across all applications) ---
    exact_counts = ev.groupby("evidence_span")["evidence_id"].transform("count")
    norm_counts = ev.groupby("_normalized_span")["evidence_id"].transform("count")

    # --- how many DISTINCT applications share this exact span (template signal) ---
    span_app_counts = ev.groupby("evidence_span")["application_id"].transform("nunique")

    # --- same application + same span duplication ---
    same_app_dup_counts = ev.groupby(["application_id", "evidence_span"])["evidence_id"].transform("count")

    # --- same communication log entry producing multiple evidence categories ---
    log_category_counts = ev.groupby("log_id")["evidence_category"].transform("nunique")
    log_multi_counts = ev.groupby("log_id")["evidence_id"].transform("count")

    ev["exact_text_duplicate_count"] = exact_counts
    ev["normalized_text_duplicate_count"] = norm_counts
    ev["same_application_duplicate"] = same_app_dup_counts.gt(1)
    ev["same_log_multi_category_count"] = log_category_counts
    ev["multi_category_span"] = log_multi_counts.gt(1) & log_category_counts.gt(1)
    ev["is_high_frequency_template"] = span_app_counts >= TEMPLATE_APPLICATION_THRESHOLD

    # --- information quality: short / generic text scores lower ---
    word_counts = ev.evidence_span.astype(str).str.split().apply(len)
    generic_pattern = re.compile(
        r"^(ok|okay|sure|yep|got it|sounds good|thanks?|thx|great|perfect|understood)\.?!?$",
        re.IGNORECASE,
    )
    is_generic = ev.evidence_span.astype(str).str.strip().apply(lambda t: bool(generic_pattern.match(t)))

    def _info_quality(row):
        if is_generic.loc[row.name] or word_counts.loc[row.name] <= 3:
            return "low"
        if word_counts.loc[row.name] <= 8 or row["is_high_frequency_template"]:
            return "medium"
        return "high"

    ev["information_quality"] = ev.apply(_info_quality, axis=1)

    # --- duplication_status classification ---
    def _dup_status(row):
        if row["same_application_duplicate"] and row["exact_text_duplicate_count"] > 1:
            return "same_application_duplicate"
        if row["is_high_frequency_template"]:
            return "likely_template"
        if row["exact_text_duplicate_count"] >= REPEATED_MIN_COUNT:
            # repeated across a modest number of applications/records but not
            # template-scale -- still potentially useful as behavioral evidence
            if row["information_quality"] == "low":
                return "potential_redundancy"
            return "repeated_but_usable"
        return "unique"

    ev["duplication_status"] = ev.apply(_dup_status, axis=1)

    def _notes(row):
        parts = []
        if row["exact_text_duplicate_count"] > 1:
            parts.append(f"exact text repeated {row['exact_text_duplicate_count']}x overall")
        if row["same_application_duplicate"]:
            parts.append("also repeated within the same application")
        if row["is_high_frequency_template"]:
            parts.append(f"appears across {span_app_counts.loc[row.name]} distinct applications "
                          f"(>= {TEMPLATE_APPLICATION_THRESHOLD} treated as template-scale)")
        if row["multi_category_span"]:
            parts.append(f"same source message produced {row['same_log_multi_category_count']} "
                          f"different evidence categories")
        if not parts:
            parts.append("no notable duplication detected")
        return "; ".join(parts)

    ev["quality_notes"] = ev.apply(_notes, axis=1)

    result_cols = [
        "evidence_id", "exact_text_duplicate_count", "normalized_text_duplicate_count",
        "same_application_duplicate", "same_log_multi_category_count", "multi_category_span",
        "is_high_frequency_template", "information_quality", "duplication_status", "quality_notes",
    ]
    result = ev[result_cols].copy()

    assert result["duplication_status"].isin(DUPLICATION_STATUSES).all()
    assert result["information_quality"].isin(INFORMATION_QUALITY_LEVELS).all()
    return result
