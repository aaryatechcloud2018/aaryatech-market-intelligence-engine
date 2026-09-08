# Behavioral Joining Intelligence — Data Foundation

This covers the data-foundation stage only: loading, schema/logical validation, and
construction of `candidate_journey_master.csv`. No behavioral analysis, mechanism
mapping, hypothesis generation, or statistical testing has been performed.

## What was loaded

Seven approved files from `data/behavioral_joining/raw/`:

```
01_candidate_applications.csv
02_communication_log.csv
03_stage_events.csv
04_clients.csv
05_recruiters.csv
06_requisitions.csv
07_data_dictionary.csv
```

`08_scenario_ground_truth.csv` is **intentionally excluded**. It is not present in
`data/behavioral_joining/raw/`, is not in the loader's `APPROVED_FILES` list, and
`data_loader.py` actively raises `PermissionError` if anything ever tries to load it
by name. This is enforced by an automated test
(`test_ground_truth_file_never_referenced_in_source`), not just a convention.

## Analytical unit

**One application = one candidate journey = one row.** `application_id` is the
primary key for analysis throughout. `candidate_id` can repeat across rows for
candidates who reapplied to a different requisition (~3% of records) — this is
expected, not a data error.

## Why communications and stage events stay separate

`candidate_journey_master.csv` deliberately does **not** flatten
`communication_log` or `stage_events` into itself. Both tables encode *sequence and
timing* — response latency between messages, the order and spacing of pipeline
stages — which is exactly the kind of structure a future behavioral-evidence pass
needs intact. Collapsing either into one row per application would destroy that
information. Instead, `candidate_journey_master.csv` carries only structured,
already-one-row-per-application fields, and downstream analysis is expected to join
back to `communication_log.csv` / `stage_events.csv` by `application_id` when it
needs sequence-level evidence.

## What `candidate_journey_master.csv` contains

2,500 rows × 47 columns. Built by merging `01_candidate_applications.csv` with
structured attributes from `06_requisitions.csv`, `04_clients.csv`, and
`05_recruiters.csv` (each source's overlapping/duplicate columns — e.g.
requisition-level job title vs. the application's own job title — were resolved by
keeping the application-level value and dropping the redundant requisition copy, so
there are no `_x`/`_y` merge artifacts).

Plus nine objective, non-behavioral derived variables:
`days_application_to_interview`, `days_interview_to_offer`, `days_offer_to_response`,
`days_acceptance_to_expected_start`, `days_expected_to_actual_start`,
`pay_change_absolute`, `pay_change_percentage`, `total_communications`,
`total_stage_events`.

A hard-coded safeguard (`derived_variables._assert_no_forbidden_columns`) raises an
exception if any column name matches `risk_score`, `probability`, `prediction`,
`mechanism`, `behavioral_`, `bias_`, or `psych` — this is enforced in code, not just
by instruction-following, and is covered by a dedicated test.

Location: `data/behavioral_joining/processed/candidate_journey_master.csv`

## Validation performed

- **File existence** — all 7 approved files present; forbidden file confirmed absent from `raw/`.
- **Schema** — expected columns present, primary keys unique/non-null, foreign keys resolve (application→requisition/client/recruiter, communications→application, stage_events→application, requisition→client), dates parse, booleans valid, categorical fields (`final_disposition`, `research_split`, `source_type`, `stage_name`) restricted to allowed value sets.
- **Logical consistency** — disposition/date/boolean cross-field rules exactly as specified (null actual_start_date where required, offer_accepted true/false rules, chronology ordering, no communications before application_date, chronologically ordered stage events).
- **Derived-variable sanity** — no negative durations on always-positive intervals, no forbidden column names.

Full results: `reports/behavioral_joining/validation_report.md`. Automated version of the same checks: `tests/behavioral_joining/` (31 tests, all passing).

## Research-split safeguard

`held_out_test` (20% of applications, stratified by disposition) was checked
**structurally only** — row count, unique/non-null `application_id`. Its outcome
distribution was not examined, tabulated, or compared against anything. It must stay
untouched until formal hypothesis testing.

## A note on "the existing Aaryatech repository"

This sandbox environment doesn't have a pre-existing Aaryatech codebase to build
inside of — each session starts from a clean filesystem. I created the requested
structure fresh (`data/`, `src/`, `reports/`, `tests/`) rather than assuming or
fabricating prior repository content. If you have an actual existing repo, these
files are structured to drop in cleanly — just confirm the target path and I'll
adjust the `RAW_DIR`/`PROCESSED_DIR`/`REPORTS_DIR` path resolution in
`data_loader.py` and `build_journey_master.py` accordingly.
