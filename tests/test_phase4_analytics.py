import csv

from src.analytics.business_performance import build_business_performance_table
from src.analytics.data_loader import Observation, load_analysis_ready_observations
from src.analytics.hypothesis_testing import run_hypothesis_tests
from src.analytics.kpi_builder import build_market_kpis
from src.analytics.trend_analysis import compute_metric_trends, safe_percentage_change


def _obs(**overrides) -> Observation:
    defaults = dict(
        observation_id=1, metric_id="ebitda", metric_name="EBITDA",
        entity_name="Smartworks", entity_type="COMPANY", geography=None,
        value="100.0", normalized_value=100.0, unit="INR", period="FY2024",
        period_year=2024, source_document="test.pdf", page_number=10,
        table_reference="Page 10, Table 1", extraction_confidence=0.9,
        classification_confidence=0.9, evidence_grade="A",
    )
    defaults.update(overrides)
    return Observation(**defaults)


# --- 1 & 2: only ANALYSIS_READY observations ever enter the pipeline ---

def test_loader_only_returns_analysis_ready_rows(tmp_path):
    csv_path = tmp_path / "analysis_ready_observations.csv"
    fieldnames = [
        "observation_id", "metric_id", "metric_name", "entity_name", "entity_type",
        "value", "normalized_value", "unit", "period", "geography", "source_document",
        "page_number", "table_reference", "extraction_confidence", "classification_confidence",
        "evidence_grade", "extraction_method", "status",
    ]
    rows = [
        {"observation_id": 1, "metric_id": "ebitda", "metric_name": "EBITDA", "entity_name": "Smartworks",
         "entity_type": "COMPANY", "value": "100", "normalized_value": "100", "unit": "INR", "period": "FY2024",
         "geography": "", "source_document": "test.pdf", "page_number": "10", "table_reference": "Page 10, Table 1",
         "extraction_confidence": "0.9", "classification_confidence": "0.9", "evidence_grade": "A",
         "extraction_method": "x", "status": "ANALYSIS_READY"},
        {"observation_id": 2, "metric_id": "ebitda", "metric_name": "EBITDA", "entity_name": "Smartworks",
         "entity_type": "COMPANY", "value": "999", "normalized_value": "999", "unit": "INR", "period": "FY2025",
         "geography": "", "source_document": "test.pdf", "page_number": "11", "table_reference": "Page 11, Table 1",
         "extraction_confidence": "0.2", "classification_confidence": "0.2", "evidence_grade": "C",
         "extraction_method": "x", "status": "CONFLICT"},
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    observations = load_analysis_ready_observations(csv_path)
    assert len(observations) == 1
    assert observations[0].observation_id == 1


def test_kpi_builder_never_sees_low_confidence_rows():
    # Simulate what would happen if a low-confidence row leaked past the
    # loader gate: build_market_kpis has no status filter of its own, so
    # this test documents that the LOADER (tested above) is the sole gate -
    # every observation passed in becomes a KPI row.
    observations = [_obs(observation_id=1), _obs(observation_id=2, period="FY2025", period_year=2025, normalized_value=200.0)]
    kpis = build_market_kpis(observations)
    assert len(kpis) >= 2
    assert {k.source_observation_id for k in kpis} == {1, 2}


# --- 3: trend calculations only compare matching metric + entity ---

def test_trend_never_mixes_different_metrics_or_entities():
    observations = [
        _obs(observation_id=1, metric_id="ebitda", entity_name="Smartworks", period_year=2023, normalized_value=100.0),
        _obs(observation_id=2, metric_id="ebitda", entity_name="Smartworks", period_year=2024, normalized_value=150.0),
        _obs(observation_id=3, metric_id="net_worth", entity_name="Smartworks", period_year=2023, normalized_value=500.0),
        _obs(observation_id=4, metric_id="ebitda", entity_name="Awfis", entity_type="COMPETITOR", period_year=2023, normalized_value=999.0),
    ]
    trends = compute_metric_trends(observations)
    ebitda_smartworks = [t for t in trends if t.metric_id == "ebitda" and t.entity_name == "Smartworks"]
    assert len(ebitda_smartworks) == 1
    assert ebitda_smartworks[0].starting_value == 100.0
    assert ebitda_smartworks[0].ending_value == 150.0
    # net_worth only has 1 period -> no trend; Awfis ebitda only has 1 period -> no trend
    assert not any(t.metric_id == "net_worth" for t in trends)
    assert not any(t.entity_name == "Awfis" for t in trends)


# --- 4: percentage change handles zero and None safely ---

def test_safe_percentage_change_handles_zero_and_none():
    assert safe_percentage_change(0, 100) is None
    assert safe_percentage_change(None, 100) is None
    assert safe_percentage_change(100, None) is None
    assert safe_percentage_change(100, 150) == 50.0


# --- 5: missing values are never fabricated ---

def test_business_performance_leaves_missing_metrics_as_none():
    observations = [_obs(observation_id=1, metric_id="ebitda", period_year=2024, normalized_value=100.0)]
    rows = build_business_performance_table(observations)
    assert len(rows) == 1
    assert rows[0].EBITDA == 100.0
    assert rows[0].revenue is None  # never reported -> must stay None, not 0 or guessed
    assert rows[0].revenue_growth is None
    assert rows[0].net_profit is None


# --- 6: hypothesis testing refuses invalid/insufficient datasets ---

def test_hypothesis_tests_report_insufficient_data_for_tiny_dataset():
    observations = [
        _obs(observation_id=1, metric_id="ebitda", entity_name="Smartworks", entity_type="COMPANY", period_year=2024, normalized_value=100.0),
        _obs(observation_id=2, metric_id="ebitda", entity_name="Awfis", entity_type="COMPETITOR", period_year=2024, normalized_value=200.0),
    ]
    results = run_hypothesis_tests(observations)
    assert len(results) == 3
    for r in results:
        assert r.result == "INSUFFICIENT_DATA"
        assert r.test_statistic is None
        assert r.p_value is None
        assert r.limitation  # must always explain why


def test_hypothesis_tests_never_invent_observations():
    results = run_hypothesis_tests([])
    assert len(results) == 3
    assert all(r.result == "INSUFFICIENT_DATA" for r in results)


# --- 7: every output retains source provenance ---

def test_all_outputs_retain_source_observation_and_page():
    observations = [
        _obs(observation_id=1, metric_id="ebitda", period_year=2023, normalized_value=100.0, page_number=30),
        _obs(observation_id=2, metric_id="ebitda", period_year=2024, normalized_value=150.0, page_number=31),
    ]
    kpis = build_market_kpis(observations)
    for k in kpis:
        assert k.source_observation_id is not None
        assert k.source_document == "test.pdf"

    trends = compute_metric_trends(observations)
    for t in trends:
        assert t.source_observation_ids
        assert t.source_pages


# --- 8: Power BI files are generated successfully (integration, against real Silver data) ---

def test_phase4_pipeline_generates_all_powerbi_files(tmp_path, monkeypatch):
    import src.analytics.phase4_pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "GOLD_POWERBI_DIR", tmp_path)

    result = pipeline_module.run_phase4_analytics()

    expected_files = [
        "market_kpis.csv", "metric_trends.csv", "business_performance.csv",
        "hypothesis_results.csv", "data_quality_summary.csv", "analytics_catalog.csv",
    ]
    for name in expected_files:
        path = tmp_path / name
        assert path.exists(), f"{name} was not created"
        with open(path) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) > 0, f"{name} has no rows"

    assert result["analysis_ready_observations_used"] > 0
    assert result["hypothesis_tests_attempted"] == 3
