# Behavioral Joining Intelligence -- Data Foundation Validation Report

Generated: 2026-08-30T11:02:11.480220+00:00

**Scope:** data foundation only. No behavioral analysis, mechanism mapping, hypothesis generation, statistical testing, or scoring was performed to produce this report.

## 1. Dataset Dimensions
- Total applications: 2500
- Unique candidates: 2414
- Total communications: 17351
- Total stage events: 17097
- Clients: 11
- Recruiters: 18
- Requisitions: 230

## 2. Outcome Counts (final_disposition)
- joined_on_time: 1074 (43.0%)
- withdrew_post_acceptance: 439 (17.6%)
- declined_offer: 406 (16.2%)
- joined_late: 295 (11.8%)
- accepted_no_show: 187 (7.5%)
- rejected_by_client: 99 (4.0%)

## 3. Research Split Counts
- discovery: 1499 (60.0%)
- held_out_test: 501 (20.0%)
- hypothesis_generation: 500 (20.0%)

**held_out_test structural check:** PASSED (501 rows, unique non-null application_id). Outcome distribution within this split was NOT examined, per the research-split safeguard.

## 4. Job Family Counts
- Administrative/Professional: 471 (18.8%)
- Healthcare: 443 (17.7%)
- Light Industrial: 427 (17.1%)
- IT/Technology: 414 (16.6%)
- Engineering: 400 (16.0%)
- Finance/Accounting: 345 (13.8%)

## 5. Client Counts
- CLI-009: 308 (12.3%)
- CLI-002: 267 (10.7%)
- CLI-011: 257 (10.3%)
- CLI-008: 238 (9.5%)
- CLI-006: 233 (9.3%)
- CLI-003: 230 (9.2%)
- CLI-001: 228 (9.1%)
- CLI-010: 196 (7.8%)
- CLI-005: 191 (7.6%)
- CLI-007: 176 (7.0%)
- CLI-004: 176 (7.0%)

## 6. Recruiter Counts (top 5 / bottom 5 by volume)
Top 5:
- REC-012: 208 (8.3%)
- REC-018: 207 (8.3%)
- REC-003: 197 (7.9%)
- REC-006: 194 (7.8%)
- REC-009: 183 (7.3%)

Bottom 5:
- REC-002: 97 (3.9%)
- REC-005: 91 (3.6%)
- REC-014: 87 (3.5%)
- REC-017: 78 (3.1%)
- REC-008: 77 (3.1%)

## 7. Missing-Value Summary (applications table)
- actual_start_date: 45.2% (expected -- only populated for joined_on_time/joined_late)
- pay_rate_prior: 15.7% (expected -- not always disclosed by candidates)

## 8. Duplicate ID Summary
- applications.application_id: 0 duplicates
- communications.log_id: 0 duplicates
- stage_events.event_id: 0 duplicates
- clients.client_account_id: 0 duplicates
- recruiters.recruiter_id: 0 duplicates
- requisitions.requisition_id: 0 duplicates

## 9. File Existence Check
PASSED: True

Errors: 0

Warnings: 0

## 10. Schema Validation
PASSED: True

Errors: 0

Warnings: 0

## 11. Logical Consistency Validation
PASSED: True

Errors: 0

Warnings: 0

## 12. Derived Variable Sanity Checks
- days_application_to_interview: min=3.00, max=21.00, mean=12.18, missing=0.0%
- days_interview_to_offer: min=2.00, max=18.00, mean=9.95, missing=0.0%
- days_offer_to_response: min=0.00, max=6.00, mean=2.92, missing=0.0%
- days_acceptance_to_expected_start: min=4.00, max=35.00, mean=19.61, missing=0.0%
- days_expected_to_actual_start: min=-1.00, max=25.00, mean=2.96, missing=45.2%
- pay_change_absolute: min=-4.00, max=14.42, mean=2.43, missing=15.7%
- pay_change_percentage: min=-6.93, max=26.62, mean=8.35, missing=15.7%
- total_communications: min=1.00, max=16.00, mean=6.94, missing=0.0%
- total_stage_events: min=4.00, max=9.00, mean=6.84, missing=0.0%
- Negative-duration violations across the four always-positive interval fields: 0 (expect 0)
- candidate_journey_master.csv shape: 2500 rows x 47 columns

- Forbidden-column safeguard: PASSED (no risk/prediction/mechanism columns present)

## Overall Result: PASSED

08_scenario_ground_truth.csv was NOT loaded, read, or referenced anywhere in this validation run.