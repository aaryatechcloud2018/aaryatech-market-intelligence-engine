# data/audience/processed/

Cleaned + quality-flagged audience data, one CSV per platform plus
`audience_master_cleaned.csv` (the merge of all four). Fully regenerated
from `data/audience/raw/` on every run of
`python -m src.audience_collection.run_collection` — see
`data/audience/README.md` for full context. Currently empty: no live
collection has run yet, so there is nothing to clean.
