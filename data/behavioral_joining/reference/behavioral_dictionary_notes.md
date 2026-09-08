# Behavioral Mechanism Library — Design Notes (V1)

## Purpose

This library is a focused reference dictionary of **behavioral mechanisms** — psychological
explanations for *why* a consumer might behave a certain way. It is Stage 1, Module 1 of the
Aaryatech Behavioral Intelligence system.

It is **not**:
- A comment dataset
- A classifier
- A sentiment scorer
- A hypothesis engine
- A source of marketing/branding recommendations

It exists so that a later module can look up a candidate explanation and check it against
defined criteria, instead of applying loosely-defined psychology terms inconsistently.

## Architecture principle: four different kinds of things

Consumer behavior involves four distinct kinds of concepts that must not be mixed into one
dictionary, because they will eventually need different scoring/analysis logic:

| Kind | Question answered | Library | Status |
|---|---|---|---|
| A. Behavioral Mechanism | *Why* might this happen? | `libraries/behavioral_library/` | **Populated in V1 (this file)** |
| B. Behavioral Signal/Outcome | *What* did the consumer do? | `libraries/behavioral_outcomes/` | Empty — future stage |
| C. Emotion | *What* did they feel? | `libraries/emotion_library/` | Empty — future stage |
| D. Context/Trigger | *What event* set it off? | `libraries/context_library/` | Empty — future stage |

A single real consumer comment will eventually be traced through all four — e.g. a **Trigger**
(redesign) disrupts a **Habit** (Mechanism), producing **Frustration** (Emotion), which may lead
to **Switching Consideration** (Outcome). This library only builds the Mechanism piece.

## Taxonomy used (Category field)

Nine categories, kept deliberately small and practical rather than exhaustively academic:

1. Decision-Making & Cognitive Biases
2. Motivation & Goals
3. Friction & Effort
4. Habit & Behavioral Persistence
5. Social Influence
6. Trust, Risk & Uncertainty
7. Identity & Self-Concept
8. Value & Reference Evaluation
9. Adoption & Resistance to Change

`Friction & Effort` and `Adoption & Resistance to Change` currently hold only one entry each
(Friction, Reactance). This is intentional for V1 — most of what would sit here is really a
*combination* of mechanisms from other categories (e.g. resistance to change is usually Status
Quo Bias + Habit Disruption + sometimes Reactance together), not a distinct mechanism of its own.
We expect these categories to grow only if a genuinely new, non-duplicate mechanism is found.

## Inclusion rule

Every candidate had to answer yes to: **"Could this concept eventually help explain WHY a
consumer behaves differently?"** and had to be something that could plausibly leave a trace in
consumer-comment text — not just a lab-only construct.

## Final V1 count

**34 mechanisms** across the 9 categories (target was 25–35).

## Decisions on the reviewed candidate list

### Kept as-is
Status Quo Bias, Loss Aversion, Social Proof, Authority Bias, Choice Overload, Friction, Habit,
Habit Disruption, Endowment Effect, Reciprocity, Scarcity, Anchoring, Confirmation Bias,
Cognitive Dissonance, Peak-End Rule, Availability Heuristic, Identity Signaling,
Self-Consistency, Commitment/Consistency, Reactance, Psychological Ownership, Goal Gradient,
Default Effect, Decoy Effect, Fairness/Equity Perception, Effort Justification,
Uncertainty/Ambiguity Aversion.

### Merged (kept as one entry, not two)
- **Bandwagon Effect** and **Herd Behavior** → merged into **Social Proof** (BM-003). All three
  describe "following the visible behavior of others" and cannot be reliably told apart from
  comment text alone. Bandwagon-style phrasing ("everyone's doing it") is documented as a
  linguistic signal of Social Proof, not a separate mechanism.
- **Familiarity Effect** → merged into **Mere Exposure Effect** (BM-009). Same observable
  phenomenon (repeated exposure → increased liking/trust) for our purposes.
- **Hyperbolic Discounting** → merged into **Present Bias** (BM-024). They produce identical
  linguistic signals in consumer comments ("I want it now, I'll deal with it later"); the
  technical distinction between them is a modeling detail, not something distinguishable from
  audience evidence.

### Excluded
- **Information Cascades** — requires observing a *sequence* of many people's choices to
  identify (each person ignoring their own signal and copying predecessors). Not identifiable
  from an individual comment. May become relevant later if we ever have population-level,
  time-ordered adoption data — out of scope for a comment-level mechanism dictionary.
- **Reference Dependence** — this is the general theoretical principle that Loss Aversion,
  Endowment Effect, and Anchoring already express in more specific, more distinguishable forms.
  Including it separately would duplicate those three entries without adding any new
  discriminable evidence.
- **Perceived Risk** and **Perceived Value** — on inspection, these are *evaluative constructs*
  (summary judgments that result from weighing several mechanisms together), not mechanisms
  themselves. Forcing them into this library would blur the "why" vs. "resulting judgment"
  distinction the whole architecture is built to preserve. Flagged as a possible future
  "evaluation constructs" concept — out of scope for Stage 1.

### Moved to a different future library
- **Trust** (bare/general) — this is an emotional/attitudinal state, not a causal mechanism.
  Belongs in the future `emotion_library/`.
- Everything explicitly listed as an outcome in the request (Switching Intention, Switching
  Behavior, Churn, Purchase, Retention, Advocacy, Recommendation) — belongs in the future
  `behavioral_outcomes/` library.
- Everything explicitly listed as an emotion (Frustration, Anger, Anxiety, Excitement, Pride,
  Disappointment) — belongs in the future `emotion_library/`.
- Everything explicitly listed as a context/trigger (App redesign, Price increase, New
  competitor, Failed transaction, Product launch) — belongs in the future `context_library/`.

### Added (missing from the original candidate list)
Identified as genuine, well-documented mechanisms with no existing entry covering them:
- **Betrayal Aversion** (BM-030) — disproportionate reaction to a loss caused by broken trust
  vs. an equivalent impersonal loss. Directly relevant to churn/switching commentary after a
  data breach, bait-and-switch, or broken promise.
- **Halo Effect** (BM-031) — a positive overall brand impression spreading to unrelated specific
  attributes. Explains "I trust this new feature because the brand is always reliable."
- **Negativity Bias** (BM-032) — negative information weighs more heavily than positive.
  Important for a system that will otherwise be tempted to average sentiment naively.
- **Variable Reward / Intermittent Reinforcement** (BM-033) — unpredictable rewards strengthen
  habitual, repeated engagement. Highly relevant to app/feature engagement patterns.
- **Sunk Cost Fallacy** (BM-034) — continuing despite dissatisfaction because of past investment.
  Common and distinguishable pattern in switching-hesitation comments ("I've put too much time
  into this to quit now").

## Distinctions between commonly confused mechanisms

These pairs/groups are easy to conflate and are explicitly documented (see each entry's
`Distinguishing_Features` field for the full detail):

- **Status Quo Bias vs. Habit vs. Habit Disruption vs. Reactance** — Status Quo Bias is a
  deliberate evaluative preference for the current option; Habit is automatic, low-thought
  behavior; Habit Disruption is the event/state of a broken automatic routine; Reactance is
  resistance specifically to a perceived loss of choice/control. A single comment can show
  several of these at once — that is expected, not a bug.
- **Loss Aversion vs. Endowment Effect vs. Sunk Cost Fallacy** — Loss Aversion is the general
  gain/loss value asymmetry; Endowment Effect is that asymmetry applied specifically to already-
  owned things; Sunk Cost Fallacy is a *decision to continue* driven by irrecoverable past
  investment, distinct from a valuation bias.
- **Social Proof vs. Authority Bias** — Social Proof is deference to the crowd/peers; Authority
  Bias is deference to a specific credentialed expert or official source.
- **Self-Consistency vs. Commitment/Consistency** — Self-Consistency is driven by a general,
  dispositional self-concept ("the kind of person I am"); Commitment/Consistency is driven by a
  specific prior stated or behavioral commitment, regardless of identity framing.
- **Effort Justification vs. Sunk Cost Fallacy** — Effort Justification changes the person's
  *valuation/attitude* toward an outcome because of invested effort; Sunk Cost Fallacy changes
  their *decision to continue*, without necessarily any attitude change.
- **Peak-End Rule vs. Negativity Bias vs. Availability Heuristic** — Peak-End Rule concerns which
  moments *within one experience* dominate memory; Negativity Bias is the general asymmetric
  weighting of negative vs. positive information; Availability Heuristic is about ease-of-recall
  driving frequency/likelihood judgments (not limited to negative examples).
- **Mere Exposure Effect vs. Halo Effect** — Mere Exposure is liking increasing from repetition
  alone; Halo Effect requires an existing positive impression transferring to a *specific,
  otherwise-unevaluated* attribute.
- **Uncertainty/Ambiguity Aversion vs. Betrayal Aversion** — Ambiguity Aversion is a preference
  for known over unknown risk *before* any bad outcome has occurred; Betrayal Aversion is the
  reaction *after* a specific trust violation has already happened.

## Evidence discipline

No mechanism should be treated as a proven fact from a single comment. Every entry carries:
- `Observable_Behavior` — general real-world signs (not comment-specific)
- `Possible_Linguistic_Signals` — illustrative example phrasings only, **not** a classification
  rule
- `Possible_Contradictory_Signals` — phrasings that would argue against the mechanism, to keep
  a future classifier honest
- `Distinguishing_Features` — required, forces explicit comparison against the nearest neighbor
- `Evidence_Requirements` — what would actually be needed to infer this mechanism reasonably

A future comment-classification module must always allow **UNKNOWN** / no-mechanism-identified
as a valid outcome. This library does not assume every comment maps to a mechanism, or that one
comment maps to only one mechanism.

## Fields deliberately excluded from this library

`Marketing_Implication`, `Branding_Implication`, `Campaign_Recommendation`,
`Business_Recommendation`, `Sentiment_Score`, `Hypothesis_Score` — all belong to later modules
(Sentiment Library, Hypothesis Engine, Marketing/Branding Interpretation layer), not to this
knowledge dictionary.
