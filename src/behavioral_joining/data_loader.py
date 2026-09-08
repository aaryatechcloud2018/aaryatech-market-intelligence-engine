"""
data_loader.py

Reusable loading module for the Aaryatech Behavioral Joining Intelligence MVP dataset.

Loads ONLY the approved analyst-facing files (01-07). 08_scenario_ground_truth.csv
is intentionally never referenced here -- it lives outside data/behavioral_joining/raw/
and must be loaded, if ever, only by a separate, explicitly-gated validation script
run after formal hypothesis testing is complete.
"""
from dataclasses import dataclass
from pathlib import Path
import pandas as pd

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "behavioral_joining" / "raw"

# Files this loader is allowed to touch. 08_scenario_ground_truth.csv is deliberately
# absent from this list -- if it's ever added here, that's a process violation.
APPROVED_FILES = {
    "applications": "01_candidate_applications.csv",
    "communications": "02_communication_log.csv",
    "stage_events": "03_stage_events.csv",
    "clients": "04_clients.csv",
    "recruiters": "05_recruiters.csv",
    "requisitions": "06_requisitions.csv",
    "data_dictionary": "07_data_dictionary.csv",
}

FORBIDDEN_FILE = "08_scenario_ground_truth.csv"

DATE_COLUMNS = {
    "applications": ["application_date", "interview_date", "offer_date", "offer_response_date",
                      "expected_start_date", "actual_start_date", "disposition_date"],
    "communications": ["timestamp"],
    "stage_events": ["stage_timestamp"],
    "requisitions": ["requisition_open_date"],
}

BOOL_COLUMNS = {
    "applications": ["offer_extended", "offer_accepted"],
}


@dataclass
class BehavioralJoiningDataset:
    """Container for all loaded, approved tables."""
    applications: pd.DataFrame
    communications: pd.DataFrame
    stage_events: pd.DataFrame
    clients: pd.DataFrame
    recruiters: pd.DataFrame
    requisitions: pd.DataFrame
    data_dictionary: pd.DataFrame

    def as_dict(self):
        return {
            "applications": self.applications,
            "communications": self.communications,
            "stage_events": self.stage_events,
            "clients": self.clients,
            "recruiters": self.recruiters,
            "requisitions": self.requisitions,
            "data_dictionary": self.data_dictionary,
        }


def _raise_if_forbidden_requested(name: str):
    if name == "ground_truth" or name == "08_scenario_ground_truth.csv":
        raise PermissionError(
            "08_scenario_ground_truth.csv is intentionally excluded from the analytical "
            "data loader. It must not be loaded during data-foundation, discovery, "
            "hypothesis-generation, or hypothesis-testing work."
        )


def load_table(name: str, raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Load a single approved table by its logical name (e.g. 'applications')."""
    _raise_if_forbidden_requested(name)
    if name not in APPROVED_FILES:
        raise KeyError(f"Unknown table '{name}'. Approved tables: {list(APPROVED_FILES)}")

    path = raw_dir / APPROVED_FILES[name]
    if not path.exists():
        raise FileNotFoundError(f"Expected raw file not found: {path}")

    df = pd.read_csv(path)

    for col in DATE_COLUMNS.get(name, []):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    for col in BOOL_COLUMNS.get(name, []):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.lower().map(
                {"true": True, "false": False}
            )

    return df


def load_dataset(raw_dir: Path = RAW_DIR) -> BehavioralJoiningDataset:
    """Load all approved tables (01-07) into a BehavioralJoiningDataset."""
    # Defensive check: make sure the forbidden file isn't accidentally sitting in
    # the raw directory in a way that some other process might pick up.
    forbidden_path = raw_dir / FORBIDDEN_FILE
    if forbidden_path.exists():
        raise PermissionError(
            f"{FORBIDDEN_FILE} was found inside {raw_dir}. It must be stored outside "
            "the analytical raw/ directory. Move it out before continuing."
        )

    tables = {name: load_table(name, raw_dir) for name in APPROVED_FILES}
    return BehavioralJoiningDataset(**tables)


if __name__ == "__main__":
    ds = load_dataset()
    for name, df in ds.as_dict().items():
        print(f"{name}: {df.shape[0]} rows x {df.shape[1]} cols")
