# Behavioral Mechanism Mapping -- QA Report

Generated: 2026-08-30T11:02:11.632064+00:00

## Mechanism library status
- Status: **LOADED**
- Source: /tmp/aaryatech-market-intelligence-engine-claude-aaryatech-market-intelligence-mvp-ow9sft/data/behavioral_joining/reference/behavioral_mechanisms.json
- Mechanisms loaded: 34

## Mapping candidates
- Total mapping records: 0
- 0 mapping records were produced. This is expected right now: mapping only runs against APPROVED/EDITED evidence, and no evidence has been human-reviewed yet (this is stage 6 of the pipeline, which runs immediately after evidence extraction with 0 approvals so far).

## What happens next
1. A human analyst reviews `behavioral_evidence_candidates.csv` and approves/edits/rejects items in `behavioral_evidence_review.csv`.
2. The real `behavioral_mechanisms.json` (34-mechanism frozen library) needs to be placed in this repository -- suggested location: `data/behavioral_joining/reference/behavioral_mechanisms.json`.
3. Once both exist, re-running the pipeline will produce real mechanism mapping candidates for human review.