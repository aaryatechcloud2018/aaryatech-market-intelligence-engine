# Behavioral Evidence Extraction -- QA Report

Generated: 2026-08-30T11:02:11.580625+00:00

**Scope:** discovery-split communications only. final_disposition, disposition_date, and actual_start_date were not available to the extractor.

## Volume
- Discovery applications: 1499 (of 2500 total)
- Discovery communications scanned: 10456
- Evidence candidates proposed: 6749
- Applications with at least one evidence candidate: 1344
- All 6749 candidates have review_status = 'pending' (expected -- nothing auto-approved): True

## Evidence by category
- candidate_questions: 788
- current_employer_activity: 589
- joining_date: 564
- certainty_uncertainty: 466
- documentation: 432
- onboarding_process: 408
- recruiter_follow_up: 376
- work_arrangement: 352
- process_delay: 334
- expectation_setting: 310
- alternative_opportunity: 299
- location_commute: 292
- schedule_shift: 262
- candidate_hesitation: 253
- commitment_language: 235
- job_security_concern: 232
- candidate_excitement: 170
- compensation_concern: 143
- responsiveness: 141
- withdrawal_language: 82
- contradictory_information: 21

## Evidence by strength
- moderate: 4421
- weak: 1358
- strong: 970

## Evidence by source type
- candidate_message: 4408
- recruiter_note: 2100
- withdrawal_statement: 144
- decline_statement: 83
- client_feedback: 14

## extractor_confidence distribution
- min=0.45, mean=0.59, max=0.75

## Traceability check
- Every evidence_span is non-empty exact source text: True
- Duplicate evidence_id count: 0 (expect 0)

## Objective signals (observational, non-scored)
- Computed for 1499 applications, 10 signal columns.
- Mean candidate messages per application: 3.51
- Mean recruiter messages per application: 3.10
- Mean unanswered candidate messages: 2.12