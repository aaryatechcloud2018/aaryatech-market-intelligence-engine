import csv

from src.analytics.executive_layer import (
    RELIABLE_OBSERVATION_IDS,
    SEMANTIC_MISMATCH_OBSERVATION_IDS,
    build_executive_kpi_snapshot,
    build_executive_trend_summary,
)

_KPI_FIELDS = [
    "kpi_name", "entity", "period", "value", "unit", "source_observation_id",
    "source_document", "page_number", "confidence",
]
_TREND_FIELDS = [
    "metric_name", "entity_name", "entity_type", "unit", "period_start", "period_end",
    "starting_value", "ending_value", "absolute_change", "percentage_change", "trend_direction",
    "source_observation_ids", "source_document", "source_pages",
]


def _kpi_row(**overrides) -> dict:
    row = {
        "kpi_name": "Number of Centers", "entity": "Smartworks", "period": "2025",
        "value": "50", "unit": "", "source_observation_id": "75",
        "source_document": "test.pdf", "page_number": "54", "confidence": "0.775",
    }
    row.update(overrides)
    return row


def _trend_row(**overrides) -> dict:
    row = {
        "metric_name": "Number of Centers", "entity_name": "Smartworks", "entity_type": "COMPANY",
        "unit": "", "period_start": "2023", "period_end": "2025",
        "starting_value": "39.0", "ending_value": "50.0", "absolute_change": "11.0",
        "percentage_change": "28.21", "trend_direction": "INCREASING",
        "source_observation_ids": "77;75", "source_document": "test.pdf", "source_pages": "54",
    }
    row.update(overrides)
    return row


# --- reliability gating ---

def test_kpi_snapshot_only_includes_reliable_observation_ids():
    reliable_id = next(iter(RELIABLE_OBSERVATION_IDS))
    unreliable_id = 999999
    assert unreliable_id not in RELIABLE_OBSERVATION_IDS

    kpi_rows = [
        _kpi_row(source_observation_id=str(reliable_id), period="2025", value="50"),
        _kpi_row(source_observation_id=str(unreliable_id), period="2024", value="9999", kpi_name="EBITDA"),
    ]
    snapshot, stats = build_executive_kpi_snapshot(kpi_rows, trend_rows=[])
    used_ids = set()
    for row in snapshot:
        used_ids.update(int(i) for i in row["source_observation_ids"].split(";"))
    assert unreliable_id not in used_ids
    assert stats.kpi_rows_excluded_unreliable_period == 1


def test_kpi_snapshot_excludes_semantic_mismatch_observation():
    mismatch_id = next(iter(SEMANTIC_MISMATCH_OBSERVATION_IDS))
    kpi_rows = [_kpi_row(kpi_name="Number of Clients", source_observation_id=str(mismatch_id))]
    snapshot, stats = build_executive_kpi_snapshot(kpi_rows, trend_rows=[])
    assert snapshot == []
    assert stats.kpi_rows_excluded_semantic_mismatch == 1


def test_kpi_snapshot_excludes_competitor_attributed_kpis():
    reliable_id = next(iter(RELIABLE_OBSERVATION_IDS))
    kpi_rows = [_kpi_row(kpi_name="Competitor Number of Centers", entity="Awfis", source_observation_id=str(reliable_id))]
    snapshot, stats = build_executive_kpi_snapshot(kpi_rows, trend_rows=[])
    assert snapshot == []
    assert stats.kpi_rows_excluded_competitor == 1


def test_trend_summary_requires_all_endpoint_ids_reliable():
    reliable_id = next(iter(RELIABLE_OBSERVATION_IDS))
    trends = [
        _trend_row(source_observation_ids=f"{reliable_id};{reliable_id}"),
        _trend_row(metric_name="EBITDA", source_observation_ids="8;9"),  # not in RELIABLE_OBSERVATION_IDS
    ]
    summary, stats = build_executive_trend_summary(trends)
    assert len(summary) == 1
    assert summary[0]["metric_name"] == "Number of Centers"
    assert stats.trend_rows_excluded_unreliable_period == 1
    assert "EBITDA (Smartworks)" in stats.excluded_trend_names


# --- no fabrication / zero-filling ---

def test_previous_period_blank_when_only_one_period_available():
    reliable_id = next(iter(RELIABLE_OBSERVATION_IDS))
    kpi_rows = [_kpi_row(kpi_name="Net Worth", period="2023", value="314.66", source_observation_id=str(reliable_id))]
    snapshot, _ = build_executive_kpi_snapshot(kpi_rows, trend_rows=[])
    assert len(snapshot) == 1
    row = snapshot[0]
    assert row["previous_period"] == ""
    assert row["previous_value"] == ""
    assert row["change"] == ""
    assert row["percentage_change"] == ""
    assert row["direction"] == ""


def test_percentage_change_is_correct_not_fabricated():
    ids = list(RELIABLE_OBSERVATION_IDS)[:2]
    kpi_rows = [
        _kpi_row(kpi_name="Number of Centers", period="2024", value="41", source_observation_id=str(ids[0])),
        _kpi_row(kpi_name="Number of Centers", period="2025", value="50", source_observation_id=str(ids[1])),
    ]
    snapshot, _ = build_executive_kpi_snapshot(kpi_rows, trend_rows=[])
    assert len(snapshot) == 1
    row = snapshot[0]
    assert row["latest_value"] == "50"
    assert row["previous_value"] == "41"
    assert row["change"] == 9.0
    assert row["percentage_change"] == round((50 - 41) / 41 * 100, 2)


# --- provenance retained ---

def test_kpi_snapshot_retains_provenance():
    reliable_id = next(iter(RELIABLE_OBSERVATION_IDS))
    kpi_rows = [_kpi_row(kpi_name="Net Worth", source_observation_id=str(reliable_id))]
    snapshot, _ = build_executive_kpi_snapshot(kpi_rows, trend_rows=[])
    row = snapshot[0]
    assert row["source_observation_ids"] != ""
    assert row["source_document"] == "test.pdf"
    assert row["source_pages"] != ""


def test_trend_summary_retains_provenance():
    reliable_id = next(iter(RELIABLE_OBSERVATION_IDS))
    trends = [_trend_row(source_observation_ids=f"{reliable_id};{reliable_id}")]
    summary, _ = build_executive_trend_summary(trends)
    row = summary[0]
    assert row["source_observation_ids"] != ""
    assert row["source_pages"] != ""


# --- integration: real Gold files, if present ---

def test_full_pipeline_against_real_gold_files_if_available(tmp_path, monkeypatch):
    import src.analytics.executive_layer as layer_module

    if not layer_module.MARKET_KPIS_CSV.exists():
        return  # Phase 4 hasn't been run in this environment - skip silently

    monkeypatch.setattr(layer_module, "EXEC_KPI_SNAPSHOT_CSV", tmp_path / "executive_kpi_snapshot.csv")
    monkeypatch.setattr(layer_module, "EXEC_TREND_SUMMARY_CSV", tmp_path / "executive_trend_summary.csv")

    result = layer_module.run_phase4_1()

    assert (tmp_path / "executive_kpi_snapshot.csv").exists()
    assert (tmp_path / "executive_trend_summary.csv").exists()

    with open(tmp_path / "executive_kpi_snapshot.csv") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for obs_id in row["source_observation_ids"].split(";"):
            assert int(obs_id) in RELIABLE_OBSERVATION_IDS
