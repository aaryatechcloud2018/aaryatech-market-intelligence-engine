from src.normalization.metric_extractor import extract_observations


def test_extract_revenue_and_ebitda():
    rows = [
        ["Particulars", "FY2025", "FY2024"],
        ["Revenue from operations", "1,234.5", "1,000.0"],
        ["EBITDA", "300.1", "250.0"],
    ]
    candidates = extract_observations(rows)
    metric_ids = {c.metric.metric_id for c in candidates}
    assert "total_revenue" in metric_ids
    assert "ebitda" in metric_ids
    # 2 columns x 2 metric rows = 4 candidate observations
    assert len(candidates) == 4


def test_extract_skips_unmatched_rows():
    rows = [
        ["Term", "Description"],
        ["Shareholders", "12345"],  # unmatched metric label, must be skipped
    ]
    candidates = extract_observations(rows)
    assert candidates == []


def test_extract_detects_period_from_header():
    rows = [
        ["Particulars", "Fiscal 2025"],
        ["Occupancy rate", "85%"],
    ]
    candidates = extract_observations(rows)
    assert len(candidates) == 1
    assert candidates[0].parsed_period.year == 2025
    assert candidates[0].parsed_value.standardized_value == 85.0
    assert candidates[0].parsed_value.standardized_unit == "%"


def test_extract_handles_two_dimensional_company_year_header():
    """
    Peer-comparison tables often span a company name across several
    columns on one header row, with year sub-headers one row below
    within that span. The merged header for a value column should
    carry BOTH the company name and the year so entity + period can
    both be recovered from the same context string.
    """
    rows = [
        ["", "Company", None, None, "Awfis Space Solutions Limited", None, None],
        [None, "2025", "2024", "2023", "2025", "2024", "2023"],
        ["EBITDA", "8,572.64", "6,596.70", "4,239.98", "4,020.00", "2,450.00", "1,760.00"],
    ]
    candidates = extract_observations(rows)
    assert len(candidates) == 6

    awfis_2025 = next(c for c in candidates if c.raw_value == "4,020.00")
    assert "Awfis" in awfis_2025.column_header
    assert "2025" in awfis_2025.column_header


def test_extract_ignores_non_numeric_cells():
    rows = [
        ["Particulars", "Status"],
        ["Number of centres", "Not disclosed"],
    ]
    candidates = extract_observations(rows)
    assert candidates == []
