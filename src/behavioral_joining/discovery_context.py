"""
discovery_context.py

Builds the OUTCOME-BLIND discovery working set used by the evidence extractor.

Hard safeguards enforced here, not just documented:
- Only research_split == "discovery" rows are ever included.
- final_disposition, disposition_date, actual_start_date are stripped before
  anything downstream can see them -- the extractor must never have outcome
  information available to it while describing behavior.
- 08_scenario_ground_truth.csv is never touched (data_loader.py already hard-blocks
  loading it by name; this module doesn't import or reference it either).
"""
from dataclasses import dataclass
import pandas as pd

from .data_loader import load_dataset, RAW_DIR
from .build_journey_master import build_master

# Columns that reveal or are derived from the final outcome. These must never reach
# the evidence extractor. offer_accepted is deliberately NOT in this list -- it's a
# process fact recruiters already knew in real time, not the eventual outcome being
# studied (joined vs. did-not-join after acceptance).
OUTCOME_COLUMNS = ["final_disposition", "disposition_date", "actual_start_date"]


@dataclass
class DiscoveryWorkingSet:
    """Outcome-blind container for the discovery-split working data."""
    applications: pd.DataFrame        # discovery-split rows, outcome columns stripped
    communications: pd.DataFrame      # discovery-split communications only
    stage_events: pd.DataFrame        # discovery-split stage events only
    n_total_applications: int         # for QA reporting only (all splits, structural count)
    n_discovery_applications: int


def build_discovery_working_set(raw_dir=RAW_DIR) -> DiscoveryWorkingSet:
    ds = load_dataset(raw_dir)
    master = build_master(raw_dir)

    n_total = len(master)
    discovery_apps = master[master.research_split == "discovery"].copy()

    # Hard strip of outcome columns -- not a filter, an actual column removal so
    # there is no way for downstream code to accidentally read them.
    present_outcome_cols = [c for c in OUTCOME_COLUMNS if c in discovery_apps.columns]
    discovery_apps = discovery_apps.drop(columns=present_outcome_cols)

    discovery_ids = set(discovery_apps.application_id)
    discovery_comms = ds.communications[ds.communications.application_id.isin(discovery_ids)].copy()
    discovery_stages = ds.stage_events[ds.stage_events.application_id.isin(discovery_ids)].copy()

    return DiscoveryWorkingSet(
        applications=discovery_apps,
        communications=discovery_comms,
        stage_events=discovery_stages,
        n_total_applications=n_total,
        n_discovery_applications=len(discovery_apps),
    )


def assert_outcome_blind(df: pd.DataFrame):
    """Raises if any outcome column has leaked into a dataframe that shouldn't have it."""
    leaked = [c for c in OUTCOME_COLUMNS if c in df.columns]
    if leaked:
        raise ValueError(f"Outcome-blindness violation: columns {leaked} present in evidence-extraction input")
