# Stage 2 — Audience Data (Wealthsimple)

## ⚠️ This repository is PUBLIC on GitHub

Before committing/pushing any file that contains real collected data
(usernames, review text, post/comment IDs, etc.), stop and think about
whether that data should be public. Confirmed via the GitHub API:
`visibility: "public"`. **Code and empty/header-only files are fine to
push. Real audience data with real public usernames is not automatically
fine just because the content originated from a public platform** — ask
before pushing a populated raw/processed/human-review CSV, per the privacy
rule the project owner set for this stage.

## v2: Feb 2026 – Jul 2026 pass (Google Play + Reddit)

Status: **code built, tested, ready to run — live collection NOT yet run
from this environment.** This cloud sandbox has no general outbound
internet access (confirmed repeatedly: direct requests to
`play.google.com`, `reddit.com`, `itunes.apple.com` are all rejected by
the environment's egress policy with a 403 policy denial — a whole-
environment restriction, not a per-platform one; see the proxy status
endpoint `http://127.0.0.1:<port>/__agentproxy/status` for the raw
evidence). Because of that, no rows have been collected in this session,
and nothing has been fabricated to look otherwise — the three v2
manual-review CSVs described below exist with the correct header row and
zero data rows.

**Run this from a machine with real internet access** (e.g. the local
Windows clone at `D:\fintech project\aaryatech-market-intelligence-engine`,
where Google Play already worked once):

```
python -m src.audience_collection.run_gp_reddit_window
```

This collects Google Play (no credentials needed) and Reddit (requires
`REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` in your local `.env` — see below),
cleans and quality-flags both, and writes:

```
data/audience/raw/google_play/wealthsimple_google_play_2026-02-01_to_2026-07-31_raw.csv
data/audience/raw/reddit/wealthsimple_reddit_2026-02-01_to_2026-07-31_raw.csv
data/audience/processed/google_play/wealthsimple_google_play_2026-02-01_to_2026-07-31_cleaned.csv
data/audience/processed/reddit/wealthsimple_reddit_2026-02-01_to_2026-07-31_cleaned.csv
data/audience/human_review/wealthsimple_google_play_feb_jul_2026_manual_review.csv
data/audience/human_review/wealthsimple_reddit_feb_jul_2026_manual_review.csv
data/audience/human_review/wealthsimple_combined_feb_jul_2026_manual_review.csv
```

Only Google Play and Reddit are touched. App Store and YouTube, and the
original `run_collection.py` (Oct–Dec 2024, all 4 platforms) flow below,
are untouched and unaffected.

### Why Reddit's old method got "403 Client Error: Blocked" — in plain language

The previous collector asked Reddit's website directly for data at a URL
like `reddit.com/r/Wealthsimple/search.json` — no login, just a plain
request, the way you'd fetch any public webpage. That used to work. Reddit
has since started actively detecting and blocking exactly this kind of
plain, unauthenticated, script-like request — it's Reddit's own anti-
scraping policy, not something wrong with our code or your internet
connection, and not something fixable by simply asking again (retrying
just risks a longer block). The only supported fix is to use Reddit's
**official API** with a login token (OAuth) — that's what this collector
now does. It never falls back to the blocked method automatically.

### Setting up Reddit credentials (needed once, ~5 minutes)

1. Go to **https://www.reddit.com/prefs/apps** (log in first).
2. Click **"create another app..."** near the bottom.
3. Give it any name (e.g. `aaryatech-research`). Select the **"script"**
   radio button (not "web app" or "installed app").
4. For "redirect uri", put anything valid — `http://localhost:8080` works.
5. Click **"create app"**. Reddit now shows you two values:
   - A short code directly under the app's name (looks random, e.g.
     `a1B2c3D4e5F6gH`) — this is your **`REDDIT_CLIENT_ID`**.
   - A longer string labeled **"secret"** — this is your
     **`REDDIT_CLIENT_SECRET`**.
6. On your Windows PC, in the repo folder
   (`D:\fintech project\aaryatech-market-intelligence-engine`), copy
   `.env.example` to a new file named exactly `.env` (if you don't already
   have one). Open `.env` in Notepad and fill in:
   ```
   REDDIT_CLIENT_ID=paste_the_short_code_here
   REDDIT_CLIENT_SECRET=paste_the_secret_here
   ```
   Save the file. `.env` is already listed in `.gitignore`, so it will
   never be committed/pushed to GitHub — safe to put real credentials in it.
7. In PowerShell, from the repo folder, run:
   ```powershell
   pip install -r requirements.txt
   python -m src.audience_collection.run_gp_reddit_window
   ```
   (The `pip install` step only needs to happen once, or after this file's
   dependencies change.)

If `.env` isn't set up yet, the script still runs — it collects Google Play
normally and prints a clear message explaining exactly what's missing for
Reddit, instead of failing silently or attempting the blocked method.

### v2 schema additions

`RAW_FIELDS` gained four columns since the original Oct–Dec 2024 build:
`record_type` (REVIEW/POST/COMMENT), `subreddit`, `post_id`, and `rating`.
The last one fixes a real bug: the original Google Play/App Store
collectors embedded the star rating INTO `comment_text` as a
`"[Rating: X/5] ..."` prefix, which technically mutated the original text.
`comment_text` now always holds the untouched original text; `rating` is
its own field.

### v2 manual-review CSVs: how to read them

Open any of the three `*_feb_jul_2026_manual_review.csv` files directly in
Excel (double-click, or Excel → Open). The first 9 columns are the only
ones you need to just read comments: **Platform, Date, Author,
Original_Text, Rating_or_Score, Thread_Title, Subreddit, Source_URL,
Quality_Status**. Everything after that is technical metadata (IDs, quality
flags) and then blank columns for your own manual coding later
(`human_read`, `human_keep`, `human_notes`, `interesting_comment`,
`possible_buyer_signal`, `possible_switching_signal`,
`possible_community_signal`) — none of which are auto-filled.

**Start with `wealthsimple_combined_feb_jul_2026_manual_review.csv`** — it
has everything from both platforms, with a `Platform` column so you can
filter/sort in Excel by Google Play vs. Reddit.

---

## v1 (legacy): Oct–Dec 2024, all 4 platforms

The original `run_collection.py` entry point, file paths, and orchestration
logic are untouched. It does, however, share the underlying collector
modules with v2 above, so two behaviors changed here too: Reddit now
requires OAuth credentials (no more silent fallback to the blocked public
endpoint), and Google Play now raises `GooglePlayFetchError` instead of
silently reporting "0 rows" on a connectivity failure. Both are strict
improvements (louder, more honest errors), not scope changes.

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

- **Reddit**: as of the v2 update above, `reddit_collector.py` no longer
  attempts the public `.json` endpoints at all (confirmed reliably blocked
  with 403) -- it requires `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` (OAuth
  via `praw`) and raises a clear, actionable error if they're missing,
  rather than silently failing. This also affects this legacy v1 flow,
  since both use the same collector module.
- **Apple App Store**: the public RSS review feed only exposes roughly the
  most recent ~500 reviews; a historical window with low review volume may
  return fewer rows than the target, which will be reported, not padded.
- **YouTube**: without a `YOUTUBE_API_KEY`, there is no way to *search* for
  videos — the collector falls back to scraping comments from a
  hand-picked seed list (`config.YOUTUBE_SEED_VIDEO_URLS`), which should be
  reviewed/expanded before a production run.
