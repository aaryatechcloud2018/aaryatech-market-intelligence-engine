# Aaryatech Behavioral Joining Intelligence — MVP Research Dataset

**Synthetic research dataset designed for Aaryatech Behavioral Joining Intelligence
methodology development. This is NOT real staffing company data and must never be
presented, cited, or implied as such.** It represents one fictional, anonymized U.S.
staffing operation, generated programmatically with a fixed random seed (`SEED = 42`)
for full reproducibility.

## What this dataset is for

This is a proof-of-concept dataset built to validate the *methodology*, not to make
claims about real candidate behavior. It exists to demonstrate that Aaryatech's
process can:
1. Discover behavioral signal from messy, realistic communication text and timing data
2. Build an evidence library from that signal
3. Compare joiners vs. non-joiners across multiple disposition types
4. Generate falsifiable behavioral hypotheses
5. Test those hypotheses on held-out data
6. Produce an auditable report

Any "finding" produced by analyzing this dataset describes patterns in the synthetic
generator, not real candidate psychology. It's useful for confirming the *method
works end to end*, not for making claims to a client.

## Files

| File | Rows | Description |
|---|---|---|
| `01_candidate_applications.csv` | 2,500 | Core table — one row per candidate application that reached offer stage. Contains outcome fields (final_disposition, dates), context fields (job, client, recruiter, pay, experience), and `research_split`. |
| `02_communication_log.csv` | 17,351 | Every recruiter/candidate communication touchpoint, timestamped, with free text. This is the primary behavioral-evidence source. |
| `03_stage_events.csv` | ~17,000 | Pipeline stage transitions per application (screened → submitted → interviews → offer → background check → onboarding → start), with timing. |
| `04_clients.csv` | 11 | Anonymized client accounts with operational tendencies (hiring speed, pay band, work-arrangement preference). |
| `05_recruiters.csv` | 18 | Anonymized recruiters with operational metadata (team, tenure, typical follow-up speed, typical communication frequency). These are neutral operational descriptors, not performance judgments. |
| `06_requisitions.csv` | 230 | Job requisitions tied to clients, spanning 6 job families. |
| `07_data_dictionary.csv` | 68 | Field-by-field definitions across every file. |
| `08_scenario_ground_truth.csv` **[PRIVATE — do not share with analysts]** | 2,500 | Which of 50 underlying generation scenarios produced each application, plus recruiter/client generation variables. Exists only to evaluate later whether the methodology recovers meaningful patterns — never for behavioral discovery itself. |

## How the tables relate

```
CLIENT ──< REQUISITION ──< APPLICATION >── CANDIDATE (via candidate_id)
                                │
                                ├──< STAGE_EVENT (ordered pipeline events)
                                └──< COMMUNICATION_LOG (ordered, timestamped, free text)

RECRUITER ──< APPLICATION
```

`application_id` is the unit of analysis. `candidate_id` can repeat (~3% of rows) to
represent candidates who reapplied to a different requisition later.

## Behavioral mechanism labels: explicitly NOT included

Per your instruction, this dataset was built from 50 realistic underlying staffing
scenarios (counteroffers, competing offers, compensation hesitation, relocation,
notice-period conflict, communication gaps, etc.) used **only** to generate diverse,
plausible evidence. Those scenario labels live exclusively in the private
`08_scenario_ground_truth.csv` file. **No file that an analyst would touch contains
any reference to Aaryatech's 34-mechanism library, any mechanism name, or any
scenario label.** This was verified programmatically (see QC report) by scanning
every analyst-facing file for mechanism-adjacent terminology and confirming zero
matches.

The mapping from behavioral evidence → Aaryatech's frozen mechanism library is a
downstream analytical step that has not been performed and should be performed
*after* the blind discovery pass described in the original architecture design.

## Research split

`research_split` in `01_candidate_applications.csv` divides applications 60/20/20
into `discovery` / `hypothesis_generation` / `held_out_test`, stratified by
`final_disposition` so each split has a proportionally similar mix of outcomes.
The `held_out_test` split must remain untouched until formal hypothesis testing —
using it earlier (even to "sanity check" a hypothesis) invalidates the audit report.

## Realistic messiness — what to expect

- Outcome categories are **not balanced** (43% joined_on_time down to 4%
  rejected_by_client) and were not forced to any target distribution.
- ~51% of applications carry medium-or-high generation "noise," meaning the stated
  reason and the surrounding evidence may not fully agree — this is intentional.
- Most individual communications are mundane ("thanks", "sounds good", short
  logistics questions) — the signal is not obvious from any single message.
- Recruiter follow-up speed and client pay band do **not** show a strong,
  clean relationship with join rate in this dataset (see QC report) — deliberately,
  so that any apparent "recruiter effect" or "pay effect" a discovery pass finds has
  to come from real signal in the text/timing data, not a crude tier lookup.
