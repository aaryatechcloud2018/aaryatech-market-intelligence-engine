"""
objective_signals.py

Computes OBJECTIVE, OBSERVATIONAL features about each application's communication/
process pattern. These are plain counts and gaps -- never risk scores, never
joining-probability, never any kind of prediction. A hard safeguard at the bottom
of this file blocks any column name that would suggest otherwise.
"""
import pandas as pd

FORBIDDEN_SUBSTRINGS = ["risk", "probability", "predict", "score", "likelihood"]


def compute_objective_signals(context) -> pd.DataFrame:
    """
    context: DiscoveryWorkingSet. Returns one row per discovery application with
    objective communication/process observations.
    """
    comms = context.communications.copy()
    apps = context.applications[["application_id"]].copy()

    comms["is_candidate"] = comms.source_type.eq("candidate_message")
    comms["is_recruiter"] = comms.source_type.isin(["recruiter_note", "interview_note"])

    agg = comms.groupby("application_id").agg(
        number_of_candidate_messages=("is_candidate", "sum"),
        number_of_recruiter_messages=("is_recruiter", "sum"),
        total_communications=("log_id", "count"),
        mean_response_latency_hours=("response_latency_hours", "mean"),
        max_response_latency_hours=("response_latency_hours", "max"),
    ).reset_index()

    # candidate/recruiter communication imbalance: simple ratio observation
    agg["candidate_recruiter_message_ratio"] = (
        agg.number_of_candidate_messages / agg.number_of_recruiter_messages.replace(0, pd.NA)
    )

    # repeated candidate follow-ups: candidate messages containing a question mark
    # sent more than once in the thread (observational count, not interpreted)
    followups = comms[comms.is_candidate & comms.text.astype(str).str.contains(r"\?", na=False)]
    followup_counts = followups.groupby("application_id").size().rename("candidate_question_message_count")
    agg = agg.merge(followup_counts, on="application_id", how="left")
    agg["candidate_question_message_count"] = agg["candidate_question_message_count"].fillna(0).astype(int)

    # unanswered candidate messages: a candidate_message with no recruiter/interview
    # note communication after it before the next candidate message or end of thread
    unanswered_counts = []
    for app_id, sub in comms.sort_values("timestamp").groupby("application_id"):
        sub = sub.reset_index(drop=True)
        unanswered = 0
        for i, row in sub.iterrows():
            if not row.is_candidate:
                continue
            following = sub.iloc[i + 1:]
            next_recruiter = following[following.is_recruiter]
            next_candidate = following[following.is_candidate]
            if len(next_recruiter) == 0:
                unanswered += 1
            elif len(next_candidate) > 0 and next_candidate.index[0] < next_recruiter.index[0]:
                unanswered += 1
        unanswered_counts.append({"application_id": app_id, "unanswered_candidate_message_count": unanswered})
    agg = agg.merge(pd.DataFrame(unanswered_counts), on="application_id", how="left")

    # stage-based signals: joining-date changes (proxy: presence of an
    # onboarding_docs_sent close to start_date vs. gaps) and stage delays
    stages = context.stage_events.copy()
    stage_counts = stages.groupby("application_id").size().rename("total_stage_events")
    agg = agg.merge(stage_counts, on="application_id", how="left")

    # days between offer_extended and the next recorded stage (observational
    # process-speed signal, not an outcome)
    def offer_to_next_stage_days(sub):
        sub = sub.sort_values("stage_timestamp")
        offer_rows = sub[sub.stage_name == "offer_extended"]
        if offer_rows.empty:
            return pd.NA
        offer_dt = offer_rows.stage_timestamp.iloc[0]
        after = sub[sub.stage_timestamp > offer_dt]
        if after.empty:
            return pd.NA
        return (after.stage_timestamp.iloc[0] - offer_dt).days

    delay_series = stages.groupby("application_id").apply(offer_to_next_stage_days, include_groups=False)
    agg = agg.merge(delay_series.rename("days_offer_to_next_stage_event"), on="application_id", how="left")

    result = apps.merge(agg, on="application_id", how="left")
    for col in ["number_of_candidate_messages", "number_of_recruiter_messages", "total_communications",
                "candidate_question_message_count", "unanswered_candidate_message_count", "total_stage_events"]:
        result[col] = result[col].fillna(0).astype(int)

    _assert_no_forbidden_columns(result)
    return result


def _assert_no_forbidden_columns(df: pd.DataFrame):
    for col in df.columns:
        low = col.lower()
        for bad in FORBIDDEN_SUBSTRINGS:
            if bad in low:
                raise ValueError(
                    f"Objective-signal safeguard triggered: column '{col}' matches forbidden "
                    f"pattern '{bad}'. Objective signals must remain observations, never scores."
                )
