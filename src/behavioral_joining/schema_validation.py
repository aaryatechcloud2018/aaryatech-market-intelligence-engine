"""
schema_validation.py

Structural schema validation for the behavioral_joining dataset:
- required files exist
- expected columns exist
- primary IDs present and unique where appropriate
- foreign keys resolve
- dates parse
- booleans are valid
- categorical outcome/enumeration fields only contain allowed values

Reports problems; does not silently fix anything.
"""
from dataclasses import dataclass, field
from pathlib import Path
import pandas as pd

from .data_loader import BehavioralJoiningDataset, RAW_DIR, APPROVED_FILES, FORBIDDEN_FILE

EXPECTED_COLUMNS = {
    "applications": [
        "candidate_id", "application_id", "requisition_id", "client_account_id", "recruiter_id",
        "job_title", "job_family", "location_city", "location_state", "work_arrangement",
        "contract_type", "years_experience", "application_source", "pay_rate_prior",
        "pay_rate_offered", "application_date", "interview_date", "offer_date",
        "offer_response_date", "expected_start_date", "actual_start_date", "offer_extended",
        "offer_accepted", "final_disposition", "disposition_date", "notice_period_days",
        "research_split",
    ],
    "communications": ["log_id", "application_id", "timestamp", "source_type", "direction",
                        "text", "word_count", "response_latency_hours"],
    "stage_events": ["event_id", "application_id", "stage_name", "stage_timestamp",
                      "days_in_prior_stage"],
    "clients": ["client_account_id", "client_name", "primary_job_families",
                "hiring_speed_tier", "pay_band_tier", "preferred_work_arrangement"],
    "recruiters": ["recruiter_id", "recruiter_first_name", "team", "tenure_months",
                    "typical_followup_speed_tier", "typical_communication_frequency_tier"],
    "requisitions": ["requisition_id", "client_account_id", "job_title", "job_family",
                      "location_city", "location_state", "work_arrangement", "contract_type",
                      "requisition_open_date"],
    "data_dictionary": ["file", "field", "type", "description"],
}

PRIMARY_KEYS = {
    "applications": "application_id",
    "communications": "log_id",
    "stage_events": "event_id",
    "clients": "client_account_id",
    "recruiters": "recruiter_id",
    "requisitions": "requisition_id",
}

FOREIGN_KEYS = [
    # (child_table, child_column, parent_table, parent_column)
    ("applications", "requisition_id", "requisitions", "requisition_id"),
    ("applications", "client_account_id", "clients", "client_account_id"),
    ("applications", "recruiter_id", "recruiters", "recruiter_id"),
    ("communications", "application_id", "applications", "application_id"),
    ("stage_events", "application_id", "applications", "application_id"),
    ("requisitions", "client_account_id", "clients", "client_account_id"),
]

DATE_COLUMNS = {
    "applications": ["application_date", "interview_date", "offer_date", "offer_response_date",
                      "expected_start_date", "actual_start_date", "disposition_date"],
    "communications": ["timestamp"],
    "stage_events": ["stage_timestamp"],
    "requisitions": ["requisition_open_date"],
}
# columns allowed to be entirely/partially null even after date parsing
NULLABLE_DATE_COLUMNS = {("applications", "actual_start_date")}

BOOL_COLUMNS = {"applications": ["offer_extended", "offer_accepted"]}

VALID_DISPOSITIONS = {
    "joined_on_time", "joined_late", "accepted_no_show",
    "withdrew_post_acceptance", "declined_offer", "rejected_by_client",
}
VALID_RESEARCH_SPLITS = {"discovery", "hypothesis_generation", "held_out_test"}
VALID_SOURCE_TYPES = {"candidate_message", "recruiter_note", "interview_note",
                       "withdrawal_statement", "decline_statement", "client_feedback"}
VALID_STAGE_NAMES = {"screened", "submitted", "client_interview_1", "client_interview_2",
                      "offer_extended", "offer_accepted", "background_check",
                      "onboarding_docs_sent", "start_date"}


@dataclass
class ValidationResult:
    passed: bool
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def add_error(self, msg):
        self.errors.append(msg)
        self.passed = False

    def add_warning(self, msg):
        self.warnings.append(msg)

    def summary(self):
        lines = [f"PASSED: {self.passed}"]
        lines.append(f"Errors: {len(self.errors)}")
        for e in self.errors:
            lines.append(f"  ERROR: {e}")
        lines.append(f"Warnings: {len(self.warnings)}")
        for w in self.warnings:
            lines.append(f"  WARNING: {w}")
        return "\n".join(lines)


def validate_files_exist(raw_dir: Path = RAW_DIR) -> ValidationResult:
    result = ValidationResult(passed=True)
    for name, fname in APPROVED_FILES.items():
        if not (raw_dir / fname).exists():
            result.add_error(f"Required file missing: {fname}")
    if (raw_dir / FORBIDDEN_FILE).exists():
        result.add_error(
            f"{FORBIDDEN_FILE} found inside {raw_dir} -- it must NOT live in the "
            "analytical raw/ directory."
        )
    return result


def validate_schema(ds: BehavioralJoiningDataset) -> ValidationResult:
    result = ValidationResult(passed=True)
    tables = ds.as_dict()

    # 1. Expected columns present
    for name, expected_cols in EXPECTED_COLUMNS.items():
        df = tables[name]
        missing = [c for c in expected_cols if c not in df.columns]
        if missing:
            result.add_error(f"[{name}] missing expected columns: {missing}")
        extra = [c for c in df.columns if c not in expected_cols]
        if extra:
            result.add_warning(f"[{name}] unexpected extra columns: {extra}")

    # 2. Primary key presence + uniqueness
    for name, pk in PRIMARY_KEYS.items():
        df = tables[name]
        if pk not in df.columns:
            result.add_error(f"[{name}] primary key column '{pk}' missing")
            continue
        n_null = df[pk].isna().sum()
        if n_null:
            result.add_error(f"[{name}] primary key '{pk}' has {n_null} null values")
        n_dup = df[pk].duplicated().sum()
        if n_dup:
            result.add_error(f"[{name}] primary key '{pk}' has {n_dup} duplicate values")

    # 3. Foreign keys resolve
    for child_tbl, child_col, parent_tbl, parent_col in FOREIGN_KEYS:
        child_df = tables[child_tbl]
        parent_df = tables[parent_tbl]
        if child_col not in child_df.columns or parent_col not in parent_df.columns:
            result.add_error(f"FK check skipped, missing column: {child_tbl}.{child_col} -> {parent_tbl}.{parent_col}")
            continue
        orphans = ~child_df[child_col].isin(parent_df[parent_col])
        n_orphan = orphans.sum()
        if n_orphan:
            result.add_error(
                f"[{child_tbl}.{child_col}] has {n_orphan} values with no match in "
                f"[{parent_tbl}.{parent_col}]"
            )

    # 4. Dates parse correctly (already coerced by loader; check for unexpected NaT)
    for name, cols in DATE_COLUMNS.items():
        df = tables[name]
        for col in cols:
            if col not in df.columns:
                continue
            n_nat = df[col].isna().sum()
            if n_nat and (name, col) not in NULLABLE_DATE_COLUMNS:
                result.add_error(f"[{name}.{col}] {n_nat} values failed to parse as dates / are null unexpectedly")

    # 5. Booleans valid
    for name, cols in BOOL_COLUMNS.items():
        df = tables[name]
        for col in cols:
            if col not in df.columns:
                continue
            bad = ~df[col].isin([True, False])
            n_bad = bad.sum()
            if n_bad:
                result.add_error(f"[{name}.{col}] {n_bad} values are not valid booleans")

    # 6. Categorical/enumeration checks
    apps = tables["applications"]
    bad_disp = ~apps["final_disposition"].isin(VALID_DISPOSITIONS)
    if bad_disp.sum():
        result.add_error(f"[applications.final_disposition] {bad_disp.sum()} values outside allowed set {VALID_DISPOSITIONS}")

    bad_split = ~apps["research_split"].isin(VALID_RESEARCH_SPLITS)
    if bad_split.sum():
        result.add_error(f"[applications.research_split] {bad_split.sum()} values outside allowed set {VALID_RESEARCH_SPLITS}")

    comms = tables["communications"]
    bad_source = ~comms["source_type"].isin(VALID_SOURCE_TYPES)
    if bad_source.sum():
        result.add_error(f"[communications.source_type] {bad_source.sum()} values outside allowed set")

    stages = tables["stage_events"]
    bad_stage = ~stages["stage_name"].isin(VALID_STAGE_NAMES)
    if bad_stage.sum():
        result.add_error(f"[stage_events.stage_name] {bad_stage.sum()} values outside allowed set")

    return result
