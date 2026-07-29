from src.normalization.table_classifier import classify_table


def test_classify_financial_table():
    rows = [
        ["Particulars", "FY2025", "FY2024"],
        ["Revenue from operations", "1,234.5", "1,000.0"],
        ["EBITDA", "300.1", "250.0"],
    ]
    result = classify_table(rows)
    assert result.category == "FINANCIAL"
    assert result.relevance_score > 0.5


def test_classify_glossary_table_as_irrelevant():
    rows = [
        ["Term", "Description"],
        ["Shareholders", "The holders of the equity shares of our Company"],
        ["RoC", "means the Registrar of Companies"],
    ]
    result = classify_table(rows)
    assert result.category == "IRRELEVANT"


def test_classify_empty_table():
    result = classify_table([])
    assert result.category == "IRRELEVANT"
    assert result.relevance_score == 0.0


def test_classify_market_table():
    rows = [
        ["Metric", "2023", "2024", "2025"],
        ["Flexible workspace market size (sq ft)", "10,000,000", "12,000,000", "15,000,000"],
        ["Market CAGR", "18%", "20%", "22%"],
    ]
    result = classify_table(rows)
    assert result.category == "MARKET"


def test_classify_risk_table_has_low_relevance():
    rows = [
        ["Risk Factor", "Description"],
        ["Litigation risk", "We are involved in certain legal proceedings"],
    ]
    result = classify_table(rows)
    assert result.category in ("RISK", "LEGAL")
    assert result.relevance_score < 0.5
