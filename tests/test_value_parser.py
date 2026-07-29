from src.normalization.value_parser import detect_period, parse_numeric_value


def test_parse_plain_integer():
    result = parse_numeric_value("583")
    assert result is not None
    assert result.standardized_value == 583.0


def test_parse_comma_separated_number():
    result = parse_numeric_value("12,500,000")
    assert result.standardized_value == 12_500_000.0


def test_parse_percentage():
    result = parse_numeric_value("45.2%")
    assert result.standardized_value == 45.2
    assert result.standardized_unit == "%"


def test_parse_parenthesized_negative():
    result = parse_numeric_value("(123.4)")
    assert result.standardized_value == -123.4


def test_parse_currency_with_crore_scale():
    result = parse_numeric_value("₹ 123.5 crore")
    assert result.standardized_unit == "INR"
    assert result.standardized_value == 123.5 * 1e7


def test_parse_currency_with_million_scale():
    result = parse_numeric_value("Rs. 45.6 Million")
    assert result.standardized_unit == "INR"
    assert result.standardized_value == 45.6 * 1e6


def test_parse_non_numeric_returns_none():
    assert parse_numeric_value("N/A") is None
    assert parse_numeric_value("-") is None
    assert parse_numeric_value("") is None
    assert parse_numeric_value(None) is None
    assert parse_numeric_value("The registered office of our Company") is None


def test_detect_period_fiscal_year():
    period = detect_period("Fiscal 2025")
    assert period.year == 2025
    assert period.period_type == "fiscal_year"


def test_detect_period_fy_short_form():
    period = detect_period("FY25")
    assert period.year == 2025


def test_detect_period_quarter():
    period = detect_period("Q1 2025")
    assert period.quarter == 1
    assert period.year == 2025


def test_detect_period_no_year_returns_none():
    assert detect_period("Total") is None
    assert detect_period(None) is None
