"""
database.py

Builds database/behavioral_joining.db -- a SEPARATE SQLite file from whatever the
existing Market Intelligence Engine uses (that engine's schema lives in
src/db/schema.py and its own database file, which this module never opens, imports,
or references). Using a distinct .db file is the safeguard here, not a shared-file
table-prefix convention -- there is no way this can collide with existing tables.

All Behavioral Joining tables are prefixed bj_ regardless, as an additional layer of
clarity if the database file were ever merged later.
"""
from pathlib import Path
import sqlite3
import pandas as pd

DB_PATH = Path(__file__).resolve().parents[2] / "database" / "behavioral_joining.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS bj_candidate_journey (
    application_id TEXT PRIMARY KEY,
    candidate_id TEXT,
    requisition_id TEXT,
    client_account_id TEXT,
    recruiter_id TEXT,
    job_title TEXT,
    job_family TEXT,
    location_city TEXT,
    location_state TEXT,
    work_arrangement TEXT,
    contract_type TEXT,
    years_experience REAL,
    application_source TEXT,
    pay_rate_prior REAL,
    pay_rate_offered REAL,
    notice_period_days INTEGER,
    application_date TEXT,
    interview_date TEXT,
    offer_date TEXT,
    offer_response_date TEXT,
    expected_start_date TEXT,
    actual_start_date TEXT,
    offer_extended INTEGER,
    offer_accepted INTEGER,
    final_disposition TEXT,
    disposition_date TEXT,
    research_split TEXT
);

CREATE TABLE IF NOT EXISTS bj_communication_log (
    log_id TEXT PRIMARY KEY,
    application_id TEXT,
    timestamp TEXT,
    source_type TEXT,
    direction TEXT,
    text TEXT,
    word_count INTEGER,
    response_latency_hours REAL
);

CREATE TABLE IF NOT EXISTS bj_stage_events (
    event_id TEXT PRIMARY KEY,
    application_id TEXT,
    stage_name TEXT,
    stage_timestamp TEXT,
    days_in_prior_stage INTEGER
);

CREATE TABLE IF NOT EXISTS bj_clients (
    client_account_id TEXT PRIMARY KEY,
    client_name TEXT,
    primary_job_families TEXT,
    hiring_speed_tier TEXT,
    pay_band_tier TEXT,
    preferred_work_arrangement TEXT
);

CREATE TABLE IF NOT EXISTS bj_recruiters (
    recruiter_id TEXT PRIMARY KEY,
    recruiter_first_name TEXT,
    team TEXT,
    tenure_months INTEGER,
    typical_followup_speed_tier TEXT,
    typical_communication_frequency_tier TEXT
);

CREATE TABLE IF NOT EXISTS bj_requisitions (
    requisition_id TEXT PRIMARY KEY,
    client_account_id TEXT,
    job_title TEXT,
    job_family TEXT,
    location_city TEXT,
    location_state TEXT,
    work_arrangement TEXT,
    contract_type TEXT,
    requisition_open_date TEXT
);

CREATE TABLE IF NOT EXISTS bj_evidence_candidates (
    evidence_id TEXT PRIMARY KEY,
    application_id TEXT,
    log_id TEXT,
    timestamp TEXT,
    source_type TEXT,
    direction TEXT,
    evidence_span TEXT,
    evidence_category TEXT,
    evidence_description TEXT,
    evidence_strength TEXT,
    context_before TEXT,
    context_after TEXT,
    response_latency_hours REAL,
    extractor_confidence REAL,
    review_status TEXT,
    reviewer_notes TEXT
);

CREATE TABLE IF NOT EXISTS bj_evidence_review (
    evidence_id TEXT PRIMARY KEY,
    application_id TEXT,
    original_evidence_span TEXT,
    original_evidence_category TEXT,
    original_evidence_description TEXT,
    original_evidence_strength TEXT,
    review_decision TEXT,
    edited_evidence_category TEXT,
    edited_evidence_description TEXT,
    edited_evidence_strength TEXT,
    reviewer TEXT,
    review_timestamp TEXT,
    reviewer_notes TEXT
);

CREATE TABLE IF NOT EXISTS bj_mechanism_reference (
    mechanism_id TEXT PRIMARY KEY,
    mechanism_name TEXT,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS bj_mechanism_mapping_candidates (
    mapping_id TEXT PRIMARY KEY,
    evidence_id TEXT,
    application_id TEXT,
    mechanism_id TEXT,
    mechanism_name TEXT,
    mapping_reason TEXT,
    evidence_support_level TEXT,
    mapping_confidence REAL,
    alternative_interpretation TEXT,
    review_status TEXT,
    reviewer_notes TEXT
);

CREATE TABLE IF NOT EXISTS bj_mechanism_mapping_review (
    mapping_id TEXT PRIMARY KEY,
    evidence_id TEXT,
    application_id TEXT,
    original_mechanism_id TEXT,
    original_mechanism_name TEXT,
    original_mapping_reason TEXT,
    original_evidence_support_level TEXT,
    original_mapping_confidence REAL,
    review_decision TEXT,
    edited_mechanism_id TEXT,
    edited_mechanism_name TEXT,
    added_alternative_interpretation TEXT,
    reviewer TEXT,
    review_timestamp TEXT,
    reviewer_notes TEXT
);

CREATE TABLE IF NOT EXISTS bj_hypotheses (
    hypothesis_id TEXT PRIMARY KEY,
    mechanism_id TEXT,
    mechanism_name TEXT,
    population TEXT,
    comparison_group TEXT,
    outcome_variable TEXT,
    hypothesis_statement TEXT,
    null_hypothesis TEXT,
    alternative_hypothesis TEXT,
    supporting_evidence_count INTEGER,
    candidate_covariates TEXT,
    proposed_statistical_test TEXT,
    status TEXT,
    analyst_notes TEXT
);

CREATE TABLE IF NOT EXISTS bj_evidence_quality (
    evidence_id TEXT PRIMARY KEY,
    exact_text_duplicate_count INTEGER,
    normalized_text_duplicate_count INTEGER,
    same_application_duplicate INTEGER,
    same_log_multi_category_count INTEGER,
    multi_category_span INTEGER,
    is_high_frequency_template INTEGER,
    information_quality TEXT,
    duplication_status TEXT,
    quality_notes TEXT
);

CREATE TABLE IF NOT EXISTS bj_evidence_review_sample (
    review_sample_id TEXT PRIMARY KEY,
    evidence_id TEXT,
    application_id TEXT,
    log_id TEXT,
    timestamp TEXT,
    source_type TEXT,
    direction TEXT,
    evidence_span TEXT,
    evidence_category TEXT,
    evidence_description TEXT,
    context_before TEXT,
    context_after TEXT,
    response_latency_hours REAL,
    extractor_confidence REAL,
    information_quality TEXT,
    duplication_status TEXT,
    human_decision TEXT,
    human_evidence_category TEXT,
    human_description TEXT,
    human_notes TEXT
);

CREATE TABLE IF NOT EXISTS bj_mechanism_review (
    mapping_id TEXT PRIMARY KEY,
    evidence_id TEXT,
    application_id TEXT,
    mechanism_id TEXT,
    mechanism_name TEXT,
    mapping_reason TEXT,
    supporting_context TEXT,
    contradictory_context TEXT,
    mapping_confidence REAL,
    alternative_mechanism_id TEXT,
    alternative_reason TEXT,
    mapping_status TEXT,
    human_mapping_decision TEXT,
    human_selected_mechanism TEXT,
    human_mapping_notes TEXT
);

CREATE TABLE IF NOT EXISTS bj_calibration_metrics (
    metric_scope TEXT,
    metric_name TEXT,
    metric_value REAL,
    computed_at TEXT
);

CREATE TABLE IF NOT EXISTS bj_hypothesis_readiness (
    mechanism_id TEXT,
    mechanism_name TEXT,
    approved_mapping_count INTEGER,
    unique_application_count INTEGER,
    unique_evidence_span_count INTEGER,
    template_share REAL,
    high_confidence_count INTEGER,
    medium_confidence_count INTEGER,
    ready_for_hypothesis_generation INTEGER,
    readiness_reason TEXT
);

CREATE TABLE IF NOT EXISTS bj_statistical_results (
    hypothesis_id TEXT,
    test_name TEXT,
    sample_size INTEGER,
    group_sizes TEXT,
    effect_size REAL,
    confidence_interval TEXT,
    test_statistic REAL,
    p_value REAL,
    multiple_testing_adjustment TEXT,
    covariates_controlled TEXT,
    result_direction TEXT,
    evidence_grade TEXT,
    limitations TEXT
);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_journey_application ON bj_candidate_journey(application_id);
CREATE INDEX IF NOT EXISTS idx_journey_candidate ON bj_candidate_journey(candidate_id);
CREATE INDEX IF NOT EXISTS idx_journey_split ON bj_candidate_journey(research_split);
CREATE INDEX IF NOT EXISTS idx_comm_application ON bj_communication_log(application_id);
CREATE INDEX IF NOT EXISTS idx_stage_application ON bj_stage_events(application_id);
CREATE INDEX IF NOT EXISTS idx_evidence_candidates_application ON bj_evidence_candidates(application_id);
CREATE INDEX IF NOT EXISTS idx_evidence_candidates_evidence_id ON bj_evidence_candidates(evidence_id);
CREATE INDEX IF NOT EXISTS idx_evidence_review_evidence_id ON bj_evidence_review(evidence_id);
CREATE INDEX IF NOT EXISTS idx_mapping_candidates_evidence_id ON bj_mechanism_mapping_candidates(evidence_id);
CREATE INDEX IF NOT EXISTS idx_mapping_candidates_mechanism_id ON bj_mechanism_mapping_candidates(mechanism_id);
CREATE INDEX IF NOT EXISTS idx_mapping_candidates_application ON bj_mechanism_mapping_candidates(application_id);
CREATE INDEX IF NOT EXISTS idx_mapping_review_mechanism_id ON bj_mechanism_mapping_review(original_mechanism_id);
CREATE INDEX IF NOT EXISTS idx_mechanism_reference_id ON bj_mechanism_reference(mechanism_id);
CREATE INDEX IF NOT EXISTS idx_hypotheses_mechanism_id ON bj_hypotheses(mechanism_id);
CREATE INDEX IF NOT EXISTS idx_evidence_quality_evidence_id ON bj_evidence_quality(evidence_id);
CREATE INDEX IF NOT EXISTS idx_review_sample_application ON bj_evidence_review_sample(application_id);
CREATE INDEX IF NOT EXISTS idx_review_sample_evidence_id ON bj_evidence_review_sample(evidence_id);
CREATE INDEX IF NOT EXISTS idx_mechanism_review_evidence_id ON bj_mechanism_review(evidence_id);
CREATE INDEX IF NOT EXISTS idx_mechanism_review_mechanism_id ON bj_mechanism_review(mechanism_id);
CREATE INDEX IF NOT EXISTS idx_mechanism_review_application ON bj_mechanism_review(application_id);
CREATE INDEX IF NOT EXISTS idx_hypothesis_readiness_mechanism_id ON bj_hypothesis_readiness(mechanism_id);
"""


def build_database(db_path: Path = DB_PATH) -> Path:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.executescript(INDEXES)
        conn.commit()
    finally:
        conn.close()
    return db_path


def load_dataframe(conn: sqlite3.Connection, df: pd.DataFrame, table_name: str):
    df.to_sql(table_name, conn, if_exists="replace", index=False)


def populate_database(db_path: Path, tables: dict, mechanism_library_result=None):
    """tables: dict of {table_name: DataFrame} for the bj_ tables that have real data
    to load right now. mechanism_library_result: a mechanism_library.MechanismLibraryResult
    -- if status != LOADED, bj_mechanism_reference is left empty (0 rows), which is the
    honest state given the source file doesn't exist yet."""
    conn = sqlite3.connect(db_path)
    try:
        for table_name, df in tables.items():
            df.to_sql(table_name, conn, if_exists="replace", index=False)

        if mechanism_library_result is not None and mechanism_library_result.status == "LOADED":
            import json
            rows = [
                {"mechanism_id": m["Pattern_ID"], "mechanism_name": m["Pattern_Name"],
                 "raw_json": json.dumps(m)}
                for m in mechanism_library_result.mechanisms
            ]
            pd.DataFrame(rows).to_sql("bj_mechanism_reference", conn, if_exists="replace", index=False)
        conn.commit()
    finally:
        conn.close()


def table_row_counts(db_path: Path = DB_PATH) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'bj_%'")
        tables = [r[0] for r in cur.fetchall()]
        counts = {}
        for t in tables:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            counts[t] = cur.fetchone()[0]
        return counts
    finally:
        conn.close()
