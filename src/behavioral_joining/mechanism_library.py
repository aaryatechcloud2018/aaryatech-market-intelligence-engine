"""
mechanism_library.py

Loads Aaryatech's existing FROZEN 34-mechanism behavioral library from
behavioral_mechanisms.json.

CRITICAL: this module NEVER creates, fabricates, or infers mechanism content. If the
file cannot be found, it returns an explicit NOT_FOUND status with the full list of
paths that were checked -- it does not raise a silent empty list, and it must never
be "helped along" by inventing plausible-sounding mechanism names. Downstream code
(mechanism_mapping.py) must treat an empty/NOT_FOUND library as a hard stop for
mapping, not as permission to guess.
"""
from dataclasses import dataclass, field
from pathlib import Path
import json

REPO_ROOT = Path(__file__).resolve().parents[2]

# Every path actually checked (see integration research notes) -- kept here so the
# search is transparent/reproducible rather than a black box.
CANDIDATE_PATHS = [
    REPO_ROOT / "behavioral_mechanisms.json",
    REPO_ROOT / "data" / "behavioral_mechanisms.json",
    REPO_ROOT / "data" / "behavioral_joining" / "reference" / "behavioral_mechanisms.json",
    REPO_ROOT / "data" / "behavioral_joining" / "behavioral_mechanisms.json",
    REPO_ROOT / "src" / "behavioral_mechanisms.json",
    REPO_ROOT / "src" / "behavioral_joining" / "behavioral_mechanisms.json",
    REPO_ROOT / "config" / "behavioral_mechanisms.json",
    REPO_ROOT / "database" / "behavioral_mechanisms.json",
    REPO_ROOT / "docs" / "behavioral_mechanisms.json",
    REPO_ROOT / "docs" / "behavioral_joining" / "behavioral_mechanisms.json",
    REPO_ROOT / "reference" / "behavioral_mechanisms.json",
]

REQUIRED_MECHANISM_FIELDS = {"Pattern_ID", "Pattern_Name"}


@dataclass
class MechanismLibraryResult:
    status: str                      # "LOADED" or "NOT_FOUND"
    mechanisms: list = field(default_factory=list)
    source_path: str = ""
    paths_checked: list = field(default_factory=list)
    error: str = ""


def load_mechanism_library(extra_paths=None, only_extra_paths: bool = False) -> MechanismLibraryResult:
    """
    only_extra_paths: when True, search ONLY extra_paths and skip CANDIDATE_PATHS
    entirely. Used for isolated unit testing of the parsing/validation logic itself,
    so tests don't depend on whether a real behavioral_mechanisms.json happens to
    exist in the repository at the time the test runs.
    """
    paths = (list(extra_paths or []) if only_extra_paths
             else list(CANDIDATE_PATHS) + list(extra_paths or []))
    checked = [str(p) for p in paths]

    for path in paths:
        if path.exists():
            try:
                data = json.loads(path.read_text())
            except json.JSONDecodeError as e:
                return MechanismLibraryResult(
                    status="NOT_FOUND", mechanisms=[], source_path=str(path),
                    paths_checked=checked,
                    error=f"Found {path} but it is not valid JSON: {e}",
                )
            mechanisms = data if isinstance(data, list) else data.get("mechanisms", data)
            if not isinstance(mechanisms, list):
                return MechanismLibraryResult(
                    status="NOT_FOUND", mechanisms=[], source_path=str(path),
                    paths_checked=checked,
                    error=f"Found {path} but its structure is not a recognizable mechanism list.",
                )
            bad = [m for m in mechanisms if not REQUIRED_MECHANISM_FIELDS.issubset(m.keys())]
            if bad:
                return MechanismLibraryResult(
                    status="NOT_FOUND", mechanisms=[], source_path=str(path),
                    paths_checked=checked,
                    error=f"Found {path} but {len(bad)} entries are missing required fields "
                          f"{REQUIRED_MECHANISM_FIELDS}.",
                )
            return MechanismLibraryResult(
                status="LOADED", mechanisms=mechanisms, source_path=str(path), paths_checked=checked,
            )

    return MechanismLibraryResult(
        status="NOT_FOUND",
        mechanisms=[],
        source_path="",
        paths_checked=checked,
        error=(
            "behavioral_mechanisms.json was not found at any checked path. The frozen "
            "34-mechanism library referenced in the project brief does not currently "
            "exist in this repository (verified by a full repository search, not just "
            "these paths). Mechanism mapping cannot run until this file is supplied. "
            "No replacement library was created, per explicit instruction."
        ),
    )
