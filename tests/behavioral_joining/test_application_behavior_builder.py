import pytest
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.behavioral_joining.application_behavior_builder import (
    build_application_behavior_bridge, BRIDGE_COLUMNS,
)


def _mapping_row(app_id, mech_id, decision="APPROVE", human_selected="", evidence_id="EV1"):
    return {
        "mapping_id": f"M-{app_id}-{evidence_id}", "evidence_id": evidence_id, "application_id": app_id,
        "mechanism_id": mech_id, "mechanism_name": "Loss Aversion",
        "mapping_reason": "r", "mapping_confidence": 0.6,
        "alternative_mechanism_id": "", "alternative_reason": "",
        "human_mapping_decision": decision, "human_selected_mechanism": human_selected,
    }


def _apps(splits):
    return pd.DataFrame([{"application_id": app_id, "research_split": split} for app_id, split in splits.items()])


def test_bridge_empty_when_no_approved_mappings():
    empty = pd.DataFrame(columns=["mapping_id", "evidence_id", "application_id", "mechanism_id",
                                   "mechanism_name", "human_mapping_decision", "human_selected_mechanism"])
    result = build_application_behavior_bridge(empty, _apps({}))
    assert len(result) == 0
    assert list(result.columns) == BRIDGE_COLUMNS


def test_bridge_one_row_per_application_mechanism_pair():
    df = pd.DataFrame([_mapping_row("APP-1", "BM-002")])
    result = build_application_behavior_bridge(df, _apps({"APP-1": "discovery"}))
    assert len(result) == 1
    assert result.iloc[0].application_id == "APP-1"
    assert result.iloc[0].mechanism_id == "BM-002"


def test_bridge_deduplicates_repeated_evidence_same_pair():
    df = pd.DataFrame([
        _mapping_row("APP-1", "BM-002", evidence_id="EV1"),
        _mapping_row("APP-1", "BM-002", evidence_id="EV2"),
    ])
    result = build_application_behavior_bridge(df, _apps({"APP-1": "discovery"}))
    assert len(result) == 1


def test_bridge_excludes_no_supported_mechanism():
    df = pd.DataFrame([_mapping_row("APP-1", "")])
    result = build_application_behavior_bridge(df, _apps({"APP-1": "discovery"}))
    assert len(result) == 0


def test_bridge_excludes_pending_and_rejected():
    df = pd.DataFrame([
        _mapping_row("APP-1", "BM-002", decision="PENDING"),
        _mapping_row("APP-2", "BM-002", decision="REJECT"),
    ])
    result = build_application_behavior_bridge(df, _apps({"APP-1": "discovery", "APP-2": "discovery"}))
    assert len(result) == 0


def test_bridge_no_evidence_text_or_confidence_columns():
    df = pd.DataFrame([_mapping_row("APP-1", "BM-002")])
    result = build_application_behavior_bridge(df, _apps({"APP-1": "discovery"}))
    assert "mapping_confidence" not in result.columns
    assert "evidence_span" not in result.columns
    assert "evidence_id" not in result.columns
    assert set(result.columns) == set(BRIDGE_COLUMNS)


def test_bridge_retains_mechanism_name():
    df = pd.DataFrame([_mapping_row("APP-1", "BM-002")])
    result = build_application_behavior_bridge(df, _apps({"APP-1": "discovery"}))
    assert result.iloc[0].mechanism_name


def test_bridge_respects_research_split_safeguard():
    df = pd.DataFrame([_mapping_row("APP-1", "BM-002")])
    result = build_application_behavior_bridge(df, _apps({"APP-1": "held_out_test"}))
    assert len(result) == 0


def test_bridge_uses_edited_mechanism_when_present():
    df = pd.DataFrame([_mapping_row("APP-1", "BM-002", decision="EDIT", human_selected="BM-005")])
    result = build_application_behavior_bridge(df, _apps({"APP-1": "discovery"}))
    assert result.iloc[0].mechanism_id == "BM-005"
