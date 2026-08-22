"""
Loader/validator for the Stage 1 Behavioral Mechanism Library.

Scope: load libraries/behavioral_library/behavioral_mechanisms.json, validate its
structure, and report duplicates/missing fields/broken references. This module does
NOT classify comments and does NOT score anything — that belongs to a later module.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LIBRARY_PATH = PROJECT_ROOT / "libraries" / "behavioral_library" / "behavioral_mechanisms.json"

REQUIRED_FIELDS = [
    "Pattern_ID",
    "Pattern_Name",
    "Category",
    "Simple_Definition",
    "Behavioral_Mechanism",
    "Typical_Trigger",
    "Observable_Behavior",
    "Possible_Linguistic_Signals",
    "Possible_Contradictory_Signals",
    "Related_Patterns",
    "Distinguishing_Features",
    "Research_Relevance",
    "Evidence_Requirements",
    "Confidence_Notes",
    "Source_References",
    "Version",
    "Status",
]


@dataclass
class ValidationReport:
    mechanism_count: int = 0
    duplicate_ids: list[str] = field(default_factory=list)
    duplicate_names: list[str] = field(default_factory=list)
    missing_fields: dict[str, list[str]] = field(default_factory=dict)
    broken_related_pattern_refs: dict[str, list[str]] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return not (
            self.duplicate_ids
            or self.duplicate_names
            or self.missing_fields
            or self.broken_related_pattern_refs
        )


def load_mechanisms(path: Path = LIBRARY_PATH) -> list[dict]:
    """Load the raw list of mechanism entries from the JSON library file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["mechanisms"]


def validate_mechanisms(mechanisms: list[dict]) -> ValidationReport:
    """Check the library for duplicate IDs/names, missing fields, and broken
    Related_Patterns references. Does not raise; callers inspect the report."""
    report = ValidationReport(mechanism_count=len(mechanisms))

    known_ids = {m.get("Pattern_ID") for m in mechanisms if m.get("Pattern_ID")}

    seen_ids: set[str] = set()
    seen_names: set[str] = set()

    for mechanism in mechanisms:
        pattern_id = mechanism.get("Pattern_ID", "<missing Pattern_ID>")

        missing = [field_name for field_name in REQUIRED_FIELDS if field_name not in mechanism]
        if missing:
            report.missing_fields[pattern_id] = missing

        if pattern_id in seen_ids:
            report.duplicate_ids.append(pattern_id)
        seen_ids.add(pattern_id)

        name = mechanism.get("Pattern_Name")
        if name:
            if name in seen_names:
                report.duplicate_names.append(name)
            seen_names.add(name)

        for ref in mechanism.get("Related_Patterns", []):
            if ref not in known_ids:
                report.broken_related_pattern_refs.setdefault(pattern_id, []).append(ref)

    return report


def print_report(report: ValidationReport) -> None:
    print(f"Mechanisms loaded: {report.mechanism_count}")
    print(f"Duplicate IDs: {report.duplicate_ids or 'none'}")
    print(f"Duplicate names: {report.duplicate_names or 'none'}")
    print(f"Entries with missing fields: {report.missing_fields or 'none'}")
    print(f"Broken Related_Patterns references: {report.broken_related_pattern_refs or 'none'}")
    print(f"Result: {'PASS' if report.is_valid else 'FAIL'}")


if __name__ == "__main__":
    mechanisms = load_mechanisms()
    report = validate_mechanisms(mechanisms)
    print_report(report)
