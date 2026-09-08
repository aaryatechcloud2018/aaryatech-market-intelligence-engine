# Aaryatech Behavioral Joining Intelligence -- Engine Status

Generated: 2026-08-30T11:02:11.632987+00:00

## Scientific chain position
```
CANDIDATE JOURNEY               [done -- Task 1]
  -> BEHAVIORAL EVIDENCE         [done -- proposed, pending human review]
  -> HUMAN VALIDATION            [NOT DONE -- waiting on you]
  -> BEHAVIORAL MECHANISM MAPPING[engine built, blocked -- no mechanism library]
  -> HUMAN VALIDATION            [not started]
  -> BEHAVIORAL HYPOTHESIS       [engine built, 0 generated -- needs approved mappings]
  -> STATISTICAL TESTING         [module built, not run]
  -> BEHAVIORAL FINDING          [none exist yet]
```

## Task 2 -- Behavioral Evidence Extraction
- Status: **complete**
- Evidence candidates: 6749
- Categories used: 21
- Review file created: 6749 rows, all 'pending'
- Items reviewed so far: 0 (expected: 0, nobody has reviewed yet)

## Task 3 -- Behavioral Mechanism Mapping
- Engine status: **built and functional**
- Mechanism library status: **LOADED**
- Mapping candidates produced: 0

## Task 4 -- Hypothesis Engine
- Engine status: **built** (src/behavioral_joining/hypothesis_engine.py)
- Hypotheses generated: 0 (correct -- requires approved mechanism mappings, which don't exist yet because Task 3 is blocked on the mechanism library)
- A single ILLUSTRATIVE example (not a real hypothesis, not saved anywhere) is available via `hypothesis_engine.demo_hypothesis_illustration()` to show the output shape.

## Task 5 -- Statistical Testing Engine (foundation)
- Module status: **built** (src/behavioral_joining/statistical_engine.py)
- Functions available: chi_square_test, fishers_exact_test, t_test, mann_whitney_u, compare_proportions, proportion_confidence_interval, logistic_regression_confounder_check, benjamini_hochberg_adjustment, grade_evidence, choose_test
- held_out_test protection: `run_held_out_validation()` requires explicit `authorized=True` + a non-empty `authorization_token` passed directly by a human; no code in this project calls it. Verified by automated test.
- No statistical test has been run against real hypotheses yet -- there are no approved hypotheses to test.

## Database
- Path: database/behavioral_joining.db (separate file from the existing engine's database)
- Row counts:
  - bj_hypotheses: 0
  - bj_calibration_metrics: 0
  - bj_statistical_results: 0
  - bj_candidate_journey: 2500
  - bj_communication_log: 17351
  - bj_stage_events: 17097
  - bj_clients: 11
  - bj_recruiters: 18
  - bj_requisitions: 230
  - bj_evidence_candidates: 6749
  - bj_evidence_review: 6749
  - bj_mechanism_mapping_candidates: 0
  - bj_mechanism_mapping_review: 0
  - bj_evidence_quality: 6749
  - bj_evidence_review_sample: 275
  - bj_mechanism_review: 0
  - bj_hypothesis_readiness: 0
  - bj_mechanism_reference: 34

## Protected data -- confirmation
- held_out_test rows were not inspected for outcome content anywhere in this run.
- final_disposition, disposition_date, actual_start_date were stripped before evidence extraction ran (outcome-blindness safeguard, automatically tested).
- 08_scenario_ground_truth.csv was not loaded (hard-blocked at the data-loader level).