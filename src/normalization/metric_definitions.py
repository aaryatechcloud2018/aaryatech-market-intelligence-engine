"""
Canonical metric registry for Market Intelligence extraction.

This is a deterministic, keyword-based registry (no LLM required, per
the MVP constraint that core extraction/normalization must work fully
offline). Each entry maps a set of row-label keyword patterns to a
standardized metric_id. Longer/more specific keywords are checked before
shorter/more generic ones so that, e.g., "ebitda margin" is not
misclassified as "ebitda".

Adding a new metric = adding a new entry here (and, if genuinely new,
a corresponding dim_metric row) - never a schema change.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MetricDefinition:
    metric_id: str
    metric_name: str
    display_name: str
    description: str
    category: str  # market / financial / operational / geographic / pricing / customer / competitor
    unit: str
    data_type: str = "numeric"
    aggregation_method: str = "latest"
    # Row-label substrings (lowercase) that identify this metric. Order
    # within a metric doesn't matter, but metric ORDER in METRIC_DEFINITIONS
    # matters - more specific metrics must be listed before more generic
    # ones they could otherwise be swallowed by.
    keywords: tuple[str, ...] = field(default_factory=tuple)


METRIC_DEFINITIONS: list[MetricDefinition] = [
    # --- Market ---
    MetricDefinition(
        "market_size", "market_size", "Market Size",
        "Total size of the addressable/served market as reported in the source.",
        "market", "INR", keywords=("market size", "total addressable market", "market opportunity"),
    ),
    MetricDefinition(
        "market_growth_rate", "market_growth_rate", "Market Growth Rate (CAGR)",
        "Compound annual growth rate of the market as reported in the source.",
        "market", "%", keywords=("cagr", "compound annual growth", "y-o-y growth", "yoy growth", "growth rate"),
    ),
    MetricDefinition(
        "market_share", "market_share", "Market Share",
        "Share of the total market attributed to a company/competitor.",
        "market", "%", keywords=("market share",),
    ),
    # --- Financial ---
    MetricDefinition(
        "ebitda_margin", "ebitda_margin", "EBITDA Margin",
        "EBITDA as a percentage of revenue.",
        "financial", "%", keywords=("ebitda margin",),
    ),
    MetricDefinition(
        "adjusted_ebitda", "adjusted_ebitda", "Adjusted EBITDA",
        "EBITDA further adjusted per the company's own definition (e.g. for lease liability cash outflows).",
        "financial", "INR", keywords=("adjusted ebitda",),
    ),
    MetricDefinition(
        "ebitda", "ebitda", "EBITDA",
        "Earnings before interest, tax, depreciation and amortization.",
        "financial", "INR", keywords=("ebitda",),
    ),
    MetricDefinition(
        "profit_margin", "profit_margin", "Profit Margin",
        "Net profit as a percentage of revenue.",
        "financial", "%", keywords=("profit margin", "pat margin", "net margin"),
    ),
    MetricDefinition(
        "net_profit", "net_profit", "Net Profit / (Loss)",
        "Profit or loss for the period, after tax.",
        "financial", "INR",
        keywords=("profit/(loss) for the year", "profit for the year", "loss for the year",
                   "profit after tax", "profit/ (loss) after tax", "net profit", "restated profit"),
    ),
    MetricDefinition(
        "total_revenue", "total_revenue", "Total Revenue",
        "Total revenue / income from operations.",
        "financial", "INR",
        keywords=("revenue from operations", "total revenue", "total income"),
    ),
    MetricDefinition(
        "total_expenses", "total_expenses", "Total Expenses",
        "Total expenses for the period.",
        "financial", "INR", keywords=("total expenses", "total expenditure"),
    ),
    MetricDefinition(
        "total_assets", "total_assets", "Total Assets",
        "Total assets as at the reporting date.",
        "financial", "INR", keywords=("total assets",),
    ),
    MetricDefinition(
        "total_borrowings", "total_borrowings", "Total Borrowings / Debt",
        "Total outstanding borrowings/debt as at the reporting date.",
        "financial", "INR", keywords=("total borrowings", "total debt"),
    ),
    MetricDefinition(
        "net_worth", "net_worth", "Net Worth",
        "Total shareholders' equity / net worth.",
        "financial", "INR", keywords=("net worth", "shareholders' equity", "total equity"),
    ),
    # --- Operational (coworking-specific) ---
    MetricDefinition(
        "occupancy_rate", "occupancy_rate", "Occupancy Rate",
        "Percentage of available seats/area that are occupied.",
        "operational", "%", keywords=("occupancy rate", "occupancy level", "occupancy"),
    ),
    MetricDefinition(
        "chargeable_seats", "chargeable_seats", "Chargeable Seats",
        "Number of seats available for billing to clients.",
        "operational", "seats", keywords=("chargeable seats", "chargeable seat capacity"),
    ),
    MetricDefinition(
        "total_seating_capacity", "total_seating_capacity", "Total Seating Capacity",
        "Total seat/desk capacity across centers.",
        "operational", "seats",
        keywords=("seating capacity", "total seats", "total desks", "seat capacity"),
    ),
    MetricDefinition(
        "number_of_centers", "number_of_centers", "Number of Centers",
        "Number of operational centers/facilities.",
        "operational", "count",
        keywords=("number of centres", "number of centers", "total centres", "total centers",
                   "operational centres", "operational centers"),
    ),
    MetricDefinition(
        "area_under_management", "area_under_management", "Area Under Management",
        "Total leasable/managed area across centers.",
        "operational", "sq_ft",
        keywords=("area under management", "leasable area", "total leased area", "super area", "carpet area"),
    ),
    MetricDefinition(
        "number_of_cities", "number_of_cities", "Number of Cities",
        "Number of distinct cities with an operational presence.",
        "geographic", "count", keywords=("number of cities", "cities of operation", "present in"),
    ),
    # --- Pricing ---
    MetricDefinition(
        "price_per_seat", "price_per_seat", "Average Price per Seat",
        "Average revenue/price realized per seat.",
        "pricing", "INR", keywords=("price per seat", "average price per seat", "arr per seat", "arpu"),
    ),
    # --- Customer ---
    MetricDefinition(
        "number_of_clients", "number_of_clients", "Number of Clients",
        "Total number of clients/customers.",
        "customer", "count", keywords=("number of clients", "total clients", "client base", "number of customers"),
    ),
    MetricDefinition(
        "client_concentration_top10", "client_concentration_top10", "Revenue Share of Top 10 Clients",
        "Percentage of revenue derived from the top 10 clients.",
        "customer", "%", keywords=("top 10 clients", "top ten clients"),
    ),
]


def get_metric_lookup() -> list[MetricDefinition]:
    """Metric definitions in priority order (most specific keywords first)."""
    return METRIC_DEFINITIONS


# --- Known entity keyword lists (used by entity resolution) -----------------
# Kept intentionally small and specific to reduce false positives; anything
# not on this list is left unresolved rather than guessed.

KNOWN_COMPETITOR_BRANDS: tuple[str, ...] = (
    "wework", "awfis", "tablespace", "table space", "indiqube", "91springboard",
    "cowrks", "co-wrks", "innov8", "regus", "iwg", "devx", "simpliwork",
    "skootr", "gowork", "the executive centre", "smartworks",
)

KNOWN_INDIAN_CITIES: tuple[str, ...] = (
    "new delhi", "delhi", "gurugram", "gurgaon", "noida", "mumbai", "navi mumbai",
    "bengaluru", "bangalore", "pune", "hyderabad", "chennai", "kolkata",
    "ahmedabad", "chandigarh", "kochi", "coimbatore", "indore", "jaipur",
    "thane", "greater noida",
)
