# Aaryatech Behavioral Joining Intelligence — Simple Guide

This is written for you, not for a programmer. If a word needs a technical
definition, this document gives it in plain English.

## 1. What Aaryatech is doing

We're trying to understand *why* some candidates who accept a job offer never
actually show up (or withdraw before day one), using two kinds of information:
the messages exchanged during recruiting, and the timing of the recruiting
process itself. The goal is to find real, testable patterns — not to build a
tool that scores or predicts any individual candidate. Every step below has a
human checkpoint built in on purpose, because the system is designed to assist
a person, not replace their judgment.

**Important:** nothing in this system has "found" anything yet. What exists
right now is the machinery to *propose* observations for a human to check —
not conclusions.

## 2. What each Python file does

All of this lives in `src/behavioral_joining/`. You never need to open these
files yourself — this section is just so you know what's there.

| File | What it does, in plain terms |
|---|---|
| `data_loader.py` | Opens the raw dataset files. Refuses to open the one file (`08_scenario_ground_truth.csv`) that must stay hidden. |
| `build_journey_master.py` | Combines everything about one candidate's application into one clean row. |
| `discovery_context.py` | Sets aside the portion of data we're allowed to explore right now, and hides the eventual outcome so we don't accidentally "cheat" by looking at the answer first. |
| `evidence_extraction.py` | Reads through candidate/recruiter messages and flags specific pieces of text that look behaviorally meaningful (e.g., "candidate re-asks about the start date"). It only *describes* what it sees — it doesn't interpret *why*. |
| `objective_signals.py` | Counts things like how many messages were exchanged and how long people took to reply — plain counts, not judgments. |
| `evidence_review.py` | The tool a human analyst uses to approve, reject, or edit each flagged piece of evidence. |
| `mechanism_library.py` | Looks for Aaryatech's official list of 34 behavioral-science explanations (the "mechanism library"). **This file doesn't exist in the repository yet** — see section 11. |
| `mechanism_mapping.py` | Once evidence is approved AND the mechanism library exists, this tries to connect approved evidence to one of the 34 explanations — carefully, not just by keyword-spotting. |
| `mechanism_mapping_review.py` | The human review tool for those proposed connections. |
| `hypothesis_engine.py` | Turns approved, mechanism-linked evidence into a formal, testable statement (a hypothesis) — but makes no claim that it's true. |
| `statistical_engine.py` | The math toolkit (statistical tests) that will eventually check whether a hypothesis holds up. It's built and tested, but hasn't been used on real hypotheses yet because there aren't any yet. |
| `database.py` | Builds a small database file to store all of this in an organized way. |
| `run_behavioral_pipeline.py` | The one command that runs everything above, in order, and prints what it's doing in plain English. |

## 3. Where the raw dataset is

`data/behavioral_joining/raw/` — the original synthetic research dataset (candidate
applications, messages, stage timing, clients, recruiters, requisitions).

## 4. Where cleaned data is

`data/behavioral_joining/processed/` — everything the pipeline builds:
`candidate_journey_master.csv`, the evidence files, and the mechanism mapping files.

## 5. What `candidate_journey_master.csv` is

One row per candidate application, with everything about that application — job,
client, recruiter, pay, dates, and final outcome — combined into a single clean
table. This was built in the previous stage (Task 1).

## 6. What `behavioral_evidence_candidates.csv` is

The AI's raw, unreviewed proposals: specific pieces of candidate/recruiter
communication that might be behaviorally meaningful, each with a plain-English
description of what was observed. Every row starts as "pending" — nothing here
has been checked by a person yet. Right now it has **6,749 rows**.

## 7. What `behavioral_evidence_review.csv` is

The human review worksheet. For each proposed piece of evidence, you (or an
analyst) can mark it **approved**, **rejected**, or **edited**. The original AI
proposal is always kept — editing never erases what the AI originally said.
**Only approved or edited evidence can move forward** to the next stage.

## 8. What the mechanism mapping files are

`mechanism_mapping_candidates.csv` and `mechanism_mapping_review.csv` work the
same way as the evidence files, but for connecting approved evidence to one of
Aaryatech's 34 official behavioral explanations. Right now these files exist
but have **0 rows**, because two things haven't happened yet: (1) no evidence
has been human-approved, and (2) the mechanism library itself isn't in the
repository (see section 11).

## 9. What `behavioral_joining.db` is

A single database file (`database/behavioral_joining.db`) that stores
everything above in one organized place, so future analysis can query it
easily instead of juggling separate CSV files. It's completely separate from
whatever database the Market Intelligence Engine already uses — think of it as
a new, clearly labeled filing cabinet sitting next to the old one, not a
drawer inside it.

## 10. What tables are inside the database

- `bj_candidate_journey`, `bj_communication_log`, `bj_stage_events`, `bj_clients`,
  `bj_recruiters`, `bj_requisitions` — the raw structured data.
- `bj_evidence_candidates`, `bj_evidence_review` — the AI proposals and human decisions.
- `bj_mechanism_reference` — the 34-mechanism library, once it exists (currently 0 rows).
- `bj_mechanism_mapping_candidates`, `bj_mechanism_mapping_review` — proposed and
  reviewed connections between evidence and mechanisms (currently 0 rows).
- `bj_hypotheses` — formal testable statements, once any exist (currently 0 rows).
- `bj_statistical_results` — test results, once any tests are run (currently 0 rows,
  and must stay that way until you approve formal testing).

## 11. What the 34-mechanism library is — and an important gap

Aaryatech's behavioral science team has (or will have) an official, fixed list
of 34 psychological/behavioral explanations — things like "people avoid
decisions that feel irreversible" — that evidence can eventually be linked to.

**I checked your actual GitHub repository directly, in full, and this file
does not exist there yet.** I did not invent one, because doing so would mean
putting words in the mouth of Aaryatech's behavioral science work — the whole
point of keeping this library "frozen" is that it comes from real expertise,
not from a script.

**What you need to do:** get the real `behavioral_mechanisms.json` file (from
wherever your behavioral science team keeps it) into this repository at
`data/behavioral_joining/reference/behavioral_mechanisms.json`. Once it's
there, re-running the pipeline will automatically pick it up and mechanism
mapping will start producing real proposals.

## 12. What still requires human review

- **All 6,749 evidence candidates** — nothing has been approved yet.
- Once evidence is approved and the mechanism library is in place, every
  mechanism mapping the system proposes.
- Every hypothesis, before it's tested.
- The final statistical results, before anyone treats them as a finding.

## 13. What has NOT yet been statistically proven

Nothing. Zero hypotheses have been generated (they require approved mechanism
mappings, which don't exist yet), and zero statistical tests have been run. The
`held_out_test` portion of the data — set aside specifically to check any
future finding fairly — has not been looked at, and the code that would
eventually analyze it is deliberately locked until you give explicit approval.

## 14. How to run the pipeline

From the main project folder, run:

```
python -m src.behavioral_joining.run_behavioral_pipeline
```

It will print 10 numbered steps as it goes, in plain language, and stop
automatically before anything that would touch protected data.

## 15. How to open/check the outputs

- **CSV files** (in `data/behavioral_joining/processed/`) open in Excel or
  Google Sheets like any spreadsheet.
- **Reports** (in `reports/behavioral_joining/`) are plain text files you can
  open in any text editor or Notepad — they end in `.md` but read like a
  normal document.
- **The database** (`database/behavioral_joining.db`) needs a SQLite viewer if
  you want to look inside directly (e.g., "DB Browser for SQLite," a free
  download) — but you generally won't need to open this yourself; it's there
  for the analysis code to use.

## 17. HOW I REVIEW THE AI'S WORK

### Why I don't review all 6,749 rows

That's too many for anyone to work through carefully, and most of them are similar
to each other anyway. Instead, the system builds a smaller, carefully chosen sample
of about 250 items for you to review — a "calibration sample." Reviewing this
smaller set tells us how well the AI's proposals hold up in general, without
requiring you to look at every single one.

### What the 250-row review sample is

It's not just 250 random or 250 "easiest" rows — it's deliberately spread across
every evidence category, a mix of confident and less-confident AI proposals, both
candidate and recruiter messages, and (importantly) some difficult, repeated, or
templated examples on purpose. If we only showed you the easy, obvious cases,
you'd approve everything and we'd learn nothing about where the AI struggles.

### What APPROVE means

You agree the AI's proposed evidence — the category and description — is a
reasonable, fair read of what's in the message. The original AI proposal is kept
either way; approving just adds your sign-off.

### What EDIT means

You agree there's *something* worth keeping here, but the AI's category or
description wasn't quite right, so you correct it. The original AI version is
never erased — your edit is saved alongside it, not instead of it.

### What REJECT means

You don't think this is meaningful evidence at all (too generic, mislabeled,
or just noise). Rejected items are excluded from everything downstream —
they can never be used for mechanism mapping.

### Why repeated text is flagged

Recruiters often reuse similar phrasing for routine updates, and some candidate
replies ("ok", "thanks") are common everywhere. That's normal and not a bug — but
it also means repeated text is usually weaker individual evidence than something
specific and unique. The system flags this (`duplication_status`,
`information_quality`) so you can weigh it accordingly, not so it gets
automatically thrown out.

### What mechanism mapping means

Once you've approved or edited some evidence, the system tries to connect it to
one of Aaryatech's 34 official behavioral explanations (e.g., "Status Quo Bias,"
"Loss Aversion"). It does this by checking the evidence category, the surrounding
conversation, and specifically checking for language that would argue *against*
a mechanism, not just language that sounds like it fits.

### Why AI cannot approve its own mapping

Every mechanism connection the AI proposes is just that — a proposal. It always
starts as `PENDING`. Nothing gets treated as real until you (a human) look at it
and approve, edit, or reject it. This mirrors the evidence review step exactly, and
for the same reason: the system is designed to assist your judgment, not replace it.

### What NO_SUPPORTED_MECHANISM means

Sometimes the AI genuinely finds no good match among the 34 mechanisms for a piece
of evidence. That's a valid, expected outcome — not a failure. The system is built
to say "we don't have a good explanation for this yet" rather than force everything
into one of the 34 categories whether it fits or not.

### When hypotheses can start

Only once enough evidence has been approved AND mapped to the same mechanism across
multiple different candidates — not just one repeated phrase. The current
thresholds for "enough" are development placeholders, clearly labeled as **not
scientifically validated** — they exist so the MVP has something concrete to work
toward, not as a scientific decision about what counts as real evidence.

### What still has NOT been statistically proven

Nothing. As of this stage, zero mechanism mappings have been human-approved (since
review hasn't started yet), so zero hypotheses have been generated, and zero
statistical tests have run. The `held_out_test` portion of the data remains
completely untouched, reserved for a future, deliberate validation step.

### Exact commands

```
python -m src.behavioral_joining.review_evidence
```
Review the 250-item evidence sample, one at a time, in your terminal. Approve,
edit, or reject each one. Saves after every single decision.

```
python -m src.behavioral_joining.run_mechanism_mapping
```
Run this after you've approved/edited some evidence. It creates mechanism mapping
proposals ONLY for the evidence you approved or edited — nothing else.

```
python -m src.behavioral_joining.review_mechanisms
```
Review the AI's proposed mechanism connections, one at a time. Approve, change the
mechanism, reject, or confirm "no mechanism applies." Saves after every decision.


## 18. New files from this stage — quick reference

| File | What it is |
|---|---|
| `data/behavioral_joining/processed/behavioral_evidence_quality.csv` | Duplication/quality flags for all 6,749 evidence items (doesn't change any original evidence). |
| `data/behavioral_joining/review/evidence_human_review_sample.csv` | The ~250-row calibration sample you actually review. |
| `data/behavioral_joining/review/mechanism_human_review.csv` | Mechanism mapping proposals for whatever you've approved/edited so far (starts empty). |
| `data/behavioral_joining/processed/hypothesis_readiness.csv` | Which of the 34 mechanisms have enough approved evidence to be worth turning into a formal hypothesis (starts empty — "waiting for human review"). |
| `reports/behavioral_joining/human_review_progress.md` | How much of the 250-row sample is reviewed, broken down by category and quality. Regenerates every time you run the review tool. |
| `reports/behavioral_joining/calibration_report.md` | How often you agreed, edited, or rejected the AI's proposals — human-review agreement, not "AI accuracy." |

## 19. What we will do next

1. You review the 250-item sample with `python -m src.behavioral_joining.review_evidence`.
2. Once you've approved/edited a meaningful number, run
   `python -m src.behavioral_joining.run_mechanism_mapping`.
3. Review those proposals with `python -m src.behavioral_joining.review_mechanisms`.
4. Once `hypothesis_readiness.csv` shows a mechanism meeting the development
   thresholds, formal hypothesis generation can begin for that mechanism —
   still no claims, just well-formed, testable questions.
5. Only after that — and only with your separate, explicit approval — does
   formal statistical testing begin, and only on the `discovery` and
   `hypothesis_generation` data. The `held_out_test` portion stays protected
   until a final, deliberate validation step that you sign off on separately.
