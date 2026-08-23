# Stage 2 — Audience Data (Wealthsimple)

## Status: system built, live collection NOT yet run

This session's sandbox has no general outbound internet access (confirmed:
direct requests to reddit.com, play.google.com, itunes.apple.com, and
youtube.com are all rejected by the environment's egress policy with a
403 policy denial — not a per-platform failure, a whole-environment one).
Because of that, **no raw comment data has been collected yet**, and none
of the CSVs described below have been fabricated to look otherwise — the
folders exist with real, tested, ready-to-run code, but zero rows.

To actually collect data: run this from an environment/session with
internet access enabled (see the Stage 2 chat summary for how to change an
environment's network policy), then run:

```
python -m src.audience_collection.run_collection
```

That single command runs every collector, cleans and quality-flags each
platform, merges them into the master dataset, and rebuilds the
human-review CSV — printing a full per-platform summary when it's done.

## Flow (never overwrite/delete raw data)

```
PUBLIC SOURCE
  -> data/audience/raw/*.csv            (append-only; existing rows never touched)
  -> data/audience/processed/*.csv      (cleaned + quality-flagged, regenerated each run)
  -> data/audience/processed/audience_master_cleaned.csv   (merge of all 4 platforms)
  -> data/audience/human_review/wealthsimple_audience_manual_review.csv
```

## Folders

- `raw/` — one CSV per platform, raw fields only (see
  `src/audience_collection/schema.py::RAW_FIELDS`). Collectors only ever
  *append* new rows here (`collectors/base.py::append_new_raw_rows`) —
  never overwrite or delete an existing row.
- `processed/` — cleaned + quality-flagged versions of each raw file (raw
  fields + `src/audience_collection/schema.py::QUALITY_FIELDS`), plus
  `audience_master_cleaned.csv`, the merge of all four. Fully regenerable
  from `raw/` — safe to overwrite on every run.
- `human_review/` — `wealthsimple_audience_manual_review.csv`, the file
  meant to be opened in Excel/Google Sheets. A fixed column subset of the
  master dataset plus blank human-fill-in columns
  (`human_read`, `human_keep`, `human_notes`, `interesting_comment`,
  `possible_buyer_signal`, `possible_switching_signal`,
  `possible_community_signal`).

## Collection window

**October 1, 2024 – December 31, 2024** — covers the national launch of
Margin Trading (Wealthsimple's first lending product, October 2024), a
real, well-documented product event with enough elapsed time for organic
comment volume to accumulate. Configurable in
`src/audience_collection/config.py`.

## Quality-flag reasoning (no dedicated "reason" column in the schema)

Every flag is a *signal*, never a verdict — nothing is deleted because of a
flag, and `possible_bot` / `possible_coordinated_post` never claim
certainty. The exact heuristic behind each flag is documented as a
docstring/comment next to where it's computed
(`src/audience_collection/cleaning/quality_flags.py`), summarized here:

- **is_exact_duplicate** — identical text (after normalization), same
  platform. All but the first occurrence are flagged.
- **near_duplicate_score** — highest textual similarity (0–1) found against
  another comment on the same platform. Purely informational — a high
  score does NOT by itself change `quality_status` or get removed, because
  a repeated narrative can mean genuine consensus, not just noise.
- **possible_spam** — >=2 URLs in the text, OR a known promotional phrase
  ("promo code", "dm me", ...), OR excessive repeated punctuation.
- **possible_bot** — the same username posting >=3 near-identical comments
  across the collected batch, OR a bot-shaped username (e.g. trailing long
  digit run, contains "bot"/"automod"). A weak heuristic signal, not proof.
- **possible_coordinated_post** — a near-duplicate text group that spans
  >=2 *different* usernames. Flagged, not removed or judged — could be
  genuine consensus, an information cascade, or coordinated amplification.
- **low_information** — cleaned text under 15 characters or 3 words.
- **irrelevant** — no brand keyword present in the text. Always `False` for
  Google Play / App Store rows (a review of the app is inherently on-topic).
- **language** — lightweight en/fr/unknown stopword-count heuristic (no
  external language-ID library — see
  `src/audience_collection/cleaning/text_utils.py` docstring for why).
- **quality_status** — a single summarizing label
  (`VALID` / `LOW_INFORMATION` / `DUPLICATE` / `POSSIBLE_SPAM` /
  `POSSIBLE_BOT` / `POSSIBLE_COORDINATED` / `IRRELEVANT` / `UNCERTAIN`),
  derived from the flags above in that priority order. `UNCERTAIN` is the
  honest fallback when there isn't enough signal either way.

## Known source limitations (documented, not hidden)

- **Reddit**: public `.json` endpoints require no login but are
  increasingly rate-limited/blocked by Reddit; the collector automatically
  switches to OAuth (via `praw`) if `REDDIT_CLIENT_ID` /
  `REDDIT_CLIENT_SECRET` env vars are set.
- **Apple App Store**: the public RSS review feed only exposes roughly the
  most recent ~500 reviews; a historical window with low review volume may
  return fewer rows than the target, which will be reported, not padded.
- **YouTube**: without a `YOUTUBE_API_KEY`, there is no way to *search* for
  videos — the collector falls back to scraping comments from a
  hand-picked seed list (`config.YOUTUBE_SEED_VIDEO_URLS`), which should be
  reviewed/expanded before a production run.
