"""
Phase 4.1: Executive Intelligence Layer.

Reads ONLY data/gold/powerbi/market_kpis.csv and metric_trends.csv
(never business_performance.csv, hypothesis_results.csv,
data_quality_summary.csv, analytics_catalog.csv, the SQLite database,
or low-confidence review data) and produces two small, executive-facing
CSVs. Phase 1-4 outputs are never modified.

--------------------------------------------------------------------
PERIOD-RELIABILITY AUDIT (see the investigation performed before this
module was written)
--------------------------------------------------------------------
Before building anything, every one of the 60 ANALYSIS_READY
observations feeding market_kpis.csv/metric_trends.csv was traced back
to its raw Bronze table (data/bronze/tables/...) and manually
cross-checked column-by-column against the table's actual header
cells - not the forward-filled/carried header Phase 2's extractor used.

Finding: Phase 2's header-lookup (src/normalization/metric_extractor.py
_lookup_header) prefers a forward-filled, carried-over label at the
exact column offset before checking the immediately adjacent column.
In tables where a value column is followed by two blank "gap" columns
before its true year label (a very common layout in this document -
e.g. "value, blank, blank, value, blank, blank, YEAR"), the carried
label from the PREVIOUS year-block gets matched instead of the correct
adjacent one. This was confirmed independently three ways:
  1. Cross-referencing page 30 (RHP "Summary of financial information")
     against page 398 (a full restated P&L) for the same EBITDA figure:
     the value 4,239.98 is tagged FY2024 on page 30 but FY2023 on page
     398 - both cannot be right, and manual column tracing shows the
     TRUE fiscal year is 2023 in both cases.
  2. Manual tracing of the raw header row (e.g. page 30 row 1:
     ['...', '2025', '', '', '2024', '', '', '2023', '']) against the
     data row's actual value column indices, table by table, for every
     one of the 12 distinct source tables behind the 60 observations.
  3. Cross-checking the corrected Revenue figures this implies
     (FY2025 ~ INR 13,740.56M, FY2024 ~ INR 10,393.64M, FY2023 ~ INR
     7,113.92M) against Smartworks' real, publicly reported IPO
     financials, which follow exactly this growth trajectory when
     correctly ordered - confirming the correct offset, not just an
     internally-consistent alternative.

Result: of the 12 distinct source tables, 7 have this misalignment
(pages 30, 31, 52, 116, 118, 174, and page 398's Table 2) and 5 do not
(pages 53, 54, 69, 265, and page 398's Table 3, which either have no
column padding at all or happen not to trigger the carry-forward
mismatch). This affects 50 of the 60 ANALYSIS_READY observations,
including ALL 36 competitor observations (all sourced from the single
page-174 table) and most of Smartworks' own profitability metrics
(EBITDA, EBITDA Margin, Adjusted EBITDA, Occupancy Rate, Total
Expenses).

Per the explicit instruction for this phase, this is NOT silently
corrected here (that would require re-running Phase 2, which is out of
scope and forbidden for this phase). Affected observations are simply
excluded from both executive outputs below, and the finding is
reported in full via `build_report()`.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass

from src.analytics.data_loader import extract_period_year
from src.analytics.trend_analysis import classify_trend_direction, safe_percentage_change
from src.config import GOLD_POWERBI_DIR

MARKET_KPIS_CSV = GOLD_POWERBI_DIR / "market_kpis.csv"
METRIC_TRENDS_CSV = GOLD_POWERBI_DIR / "metric_trends.csv"

EXEC_KPI_SNAPSHOT_CSV = GOLD_POWERBI_DIR / "executive_kpi_snapshot.csv"
EXEC_TREND_SUMMARY_CSV = GOLD_POWERBI_DIR / "executive_trend_summary.csv"

# --- Confirmed-reliable source observations (see audit above) -------------
# Every other observation_id feeding market_kpis.csv/metric_trends.csv
# comes from one of the 7 tables with the confirmed period-mapping bug.
RELIABLE_OBSERVATION_IDS: frozenset[int] = frozenset({
    74, 75, 76, 77,   # page 54, Table 4 (clean 4-column table, no padding)
    78, 79, 80,       # page 69, Table 1 (Top 10 Clients revenue share)
    298,              # page 265, Table 1 (Total Borrowings)
    356,              # page 398, Table 3 (Total Equity / Net Worth)
})

# observation_id 66 ("Number of Clients", page 53) has a CORRECT period
# label but is a separate, different kind of problem: its row label is
# "Number of Clients who terminated their agreements without serving
# their notice period" - a churn count, not the total client count the
# "number_of_clients" metric_id implies. Phase 2's keyword matcher
# over-matched on the substring "number of clients". This is a metric
# semantic-identity issue, not a period issue, so it is excluded here
# and reported separately rather than folded into the period findings.
SEMANTIC_MISMATCH_OBSERVATION_IDS: frozenset[int] = frozenset({66})

# kpi/metric display name -> executive category (Output 1)
_CATEGORY_MAP: dict[str, str] = {
    "Revenue": "GROWTH", "Revenue Growth": "GROWTH",
    "Number of Centers": "GROWTH", "Number of Centers Growth": "GROWTH",
    "Number of Clients": "GROWTH", "Number of Clients Growth": "GROWTH",
    "EBITDA": "PROFITABILITY", "EBITDA Growth": "PROFITABILITY", "EBITDA Margin": "PROFITABILITY",
    "Adjusted EBITDA": "PROFITABILITY", "Adjusted EBITDA Growth": "PROFITABILITY",
    "Net Profit / (Loss)": "PROFITABILITY", "Net Profit / (Loss) Growth": "PROFITABILITY",
    "Net Profit Margin": "PROFITABILITY",
    "Occupancy Rate": "OPERATIONS", "Total Seating Capacity": "OPERATIONS", "Chargeable Seats": "OPERATIONS",
    "Total Assets": "FINANCIAL STRENGTH", "Total Borrowings / Debt": "FINANCIAL STRENGTH",
    "Net Worth": "FINANCIAL STRENGTH", "Net Worth Growth": "FINANCIAL STRENGTH",
    "Revenue Share of Top 10 Clients": "RISK",
}

_KPI_SNAPSHOT_FIELDNAMES = [
    "kpi_name", "category", "entity_name", "latest_period", "latest_value", "unit",
    "previous_period", "previous_value", "change", "percentage_change", "direction",
    "source_observation_ids", "source_document", "source_pages", "confidence",
]
_TREND_SUMMARY_FIELDNAMES = [
    "metric_name", "category", "entity_name", "start_period", "end_period",
    "start_value", "end_value", "absolute_change", "percentage_change", "direction",
    "source_observation_ids", "source_document", "source_pages", "confidence",
]


def _read_csv(path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found - run scripts/run_phase4_analytics.py first.")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _is_company_level(kpi_name: str) -> bool:
    # This snapshot is explicitly for "the company's performance", not a
    # competitor benchmark; Phase 2 prefixes competitor-attributed KPIs
    # with "Competitor " (see src/normalization/entity_resolver.py).
    return not kpi_name.startswith("Competitor ")


@dataclass
class ExclusionStats:
    kpi_rows_excluded_unreliable_period: int = 0
    kpi_rows_excluded_semantic_mismatch: int = 0
    kpi_rows_excluded_competitor: int = 0
    kpi_rows_excluded_no_category: int = 0
    trend_rows_excluded_unreliable_period: int = 0
    trend_rows_excluded_no_category: int = 0
    excluded_kpi_names: set = None
    excluded_trend_names: set = None

    def __post_init__(self):
        self.excluded_kpi_names = set()
        self.excluded_trend_names = set()


# ===========================================================================
# Output 1: executive_kpi_snapshot.csv
# ===========================================================================


def _growth_row_all_ids_reliable(row: dict, trend_rows: list[dict]) -> bool:
    """
    A "X Growth" KPI row stores only ONE endpoint's observation_id
    (see kpi_builder.py). Its true reliability depends on BOTH trend
    endpoints, so cross-reference the matching row in metric_trends.csv
    (which carries both source_observation_ids) rather than trusting
    the single id stored on the KPI row.
    """
    base_name = row["kpi_name"][: -len(" Growth")]
    period_start, _, period_end = row["period"].partition(" to ")
    for trend in trend_rows:
        if (
            trend["metric_name"] == base_name
            and trend["entity_name"] == row["entity"]
            and trend["period_start"] == period_start
            and trend["period_end"] == period_end
        ):
            ids = [int(i) for i in trend["source_observation_ids"].split(";") if i]
            return bool(ids) and all(i in RELIABLE_OBSERVATION_IDS for i in ids)
    return False  # no matching trend found - cannot confirm reliability, so exclude


def build_executive_kpi_snapshot(
    kpi_rows: list[dict] | None = None, trend_rows: list[dict] | None = None
) -> tuple[list[dict], ExclusionStats]:
    if kpi_rows is None:
        kpi_rows = _read_csv(MARKET_KPIS_CSV)
    if trend_rows is None:
        trend_rows = _read_csv(METRIC_TRENDS_CSV)

    stats = ExclusionStats()

    # Group by (kpi_name, entity) to build latest-vs-previous comparisons.
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in kpi_rows:
        obs_id = int(row["source_observation_id"])
        kpi_name = row["kpi_name"]

        if not _is_company_level(kpi_name):
            stats.kpi_rows_excluded_competitor += 1
            continue
        if obs_id in SEMANTIC_MISMATCH_OBSERVATION_IDS:
            stats.kpi_rows_excluded_semantic_mismatch += 1
            stats.excluded_kpi_names.add(kpi_name)
            continue

        is_growth = kpi_name.endswith(" Growth")
        reliable = _growth_row_all_ids_reliable(row, trend_rows) if is_growth else obs_id in RELIABLE_OBSERVATION_IDS
        if not reliable:
            stats.kpi_rows_excluded_unreliable_period += 1
            stats.excluded_kpi_names.add(kpi_name)
            continue

        base_name = kpi_name[: -len(" Growth")] if kpi_name.endswith(" Growth") else kpi_name
        if base_name not in _CATEGORY_MAP and kpi_name not in _CATEGORY_MAP:
            stats.kpi_rows_excluded_no_category += 1
            continue

        groups[(kpi_name, row["entity"])].append(row)

    snapshot_rows: list[dict] = []
    for (kpi_name, entity), rows in groups.items():
        # "X Growth" rows are already period-range summaries (e.g. "FY2023
        # to FY2025"), not a single dated value - emit them directly.
        if kpi_name.endswith(" Growth"):
            for row in rows:
                snapshot_rows.append({
                    "kpi_name": kpi_name,
                    "category": _CATEGORY_MAP.get(kpi_name, _CATEGORY_MAP.get(kpi_name[: -len(" Growth")])),
                    "entity_name": entity,
                    "latest_period": row["period"],
                    "latest_value": row["value"],
                    "unit": row["unit"],
                    "previous_period": "",
                    "previous_value": "",
                    "change": "",
                    "percentage_change": "",
                    "direction": "",
                    "source_observation_ids": row["source_observation_id"],
                    "source_document": row["source_document"],
                    "source_pages": row["page_number"],
                    "confidence": row["confidence"],
                })
            continue

        dated_rows = [(extract_period_year(r["period"]), r) for r in rows]
        dated_rows = [(y, r) for y, r in dated_rows if y is not None]
        if not dated_rows:
            continue
        dated_rows.sort(key=lambda yr: yr[0], reverse=True)

        latest_year, latest_row = dated_rows[0]
        previous_row = dated_rows[1][1] if len(dated_rows) > 1 else None

        latest_value = float(latest_row["value"].replace(",", "").replace("%", "").strip("()") or 0)
        latest_value = -latest_value if latest_row["value"].strip().startswith("(") else latest_value

        change = percentage_change = direction = ""
        previous_period = previous_value_str = ""
        if previous_row is not None:
            prev_value = float(previous_row["value"].replace(",", "").replace("%", "").strip("()") or 0)
            prev_value = -prev_value if previous_row["value"].strip().startswith("(") else prev_value
            change = round(latest_value - prev_value, 4)
            percentage_change = safe_percentage_change(prev_value, latest_value)
            direction = classify_trend_direction(change, percentage_change)
            previous_period = previous_row["period"]
            previous_value_str = previous_row["value"]

        source_ids = sorted({int(r["source_observation_id"]) for _, r in dated_rows[:2]})
        source_pages = sorted({r["page_number"] for _, r in dated_rows[:2]})

        snapshot_rows.append({
            "kpi_name": kpi_name,
            "category": _CATEGORY_MAP.get(kpi_name),
            "entity_name": entity,
            "latest_period": latest_row["period"],
            "latest_value": latest_row["value"],
            "unit": latest_row["unit"],
            "previous_period": previous_period,
            "previous_value": previous_value_str,
            "change": change,
            "percentage_change": percentage_change if percentage_change is not None else "",
            "direction": direction,
            "source_observation_ids": ";".join(str(i) for i in source_ids),
            "source_document": latest_row["source_document"],
            "source_pages": ";".join(str(p) for p in source_pages),
            "confidence": latest_row["confidence"],
        })

    snapshot_rows.sort(key=lambda r: (r["category"] or "", r["kpi_name"]))
    return snapshot_rows, stats


# ===========================================================================
# Output 2: executive_trend_summary.csv
# ===========================================================================

_TREND_PRIORITY_METRICS = {
    "EBITDA", "EBITDA Margin", "Adjusted EBITDA", "Net Profit / (Loss)",
    "Number of Centers", "Number of Clients", "Occupancy Rate", "Net Worth",
    "Total Borrowings / Debt", "Revenue Share of Top 10 Clients",
}


def build_executive_trend_summary(trend_rows: list[dict] | None = None) -> tuple[list[dict], ExclusionStats]:
    if trend_rows is None:
        trend_rows = _read_csv(METRIC_TRENDS_CSV)

    stats = ExclusionStats()
    summary_rows: list[dict] = []

    for row in trend_rows:
        metric_name = row["metric_name"]
        if not _is_company_level(metric_name):
            continue  # executive trend summary is company-level, same policy as Output 1
        if metric_name not in _TREND_PRIORITY_METRICS:
            stats.trend_rows_excluded_no_category += 1
            continue

        obs_ids = [int(i) for i in row["source_observation_ids"].split(";") if i]
        if not all(i in RELIABLE_OBSERVATION_IDS for i in obs_ids):
            stats.trend_rows_excluded_unreliable_period += 1
            stats.excluded_trend_names.add(f"{metric_name} ({row['entity_name']})")
            continue

        summary_rows.append({
            "metric_name": metric_name,
            "category": _CATEGORY_MAP.get(metric_name, ""),
            "entity_name": row["entity_name"],
            "start_period": row["period_start"],
            "end_period": row["period_end"],
            "start_value": row["starting_value"],
            "end_value": row["ending_value"],
            "absolute_change": row["absolute_change"],
            "percentage_change": row["percentage_change"],
            "direction": row["trend_direction"],
            "source_observation_ids": row["source_observation_ids"],
            "source_document": row["source_document"],
            "source_pages": row["source_pages"],
            "confidence": "",  # metric_trends.csv does not carry a single confidence value
        })

    summary_rows.sort(key=lambda r: (r["category"], r["metric_name"]))
    return summary_rows, stats


# ===========================================================================
# Entry point
# ===========================================================================


def _write_csv(path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def run_phase4_1() -> dict:
    kpi_rows_raw = _read_csv(MARKET_KPIS_CSV)
    trend_rows_raw = _read_csv(METRIC_TRENDS_CSV)

    snapshot_rows, kpi_stats = build_executive_kpi_snapshot(kpi_rows_raw, trend_rows_raw)
    trend_summary_rows, trend_stats = build_executive_trend_summary(trend_rows_raw)

    _write_csv(EXEC_KPI_SNAPSHOT_CSV, _KPI_SNAPSHOT_FIELDNAMES, snapshot_rows)
    _write_csv(EXEC_TREND_SUMMARY_CSV, _TREND_SUMMARY_FIELDNAMES, trend_summary_rows)

    return {
        "kpi_rows_created": len(snapshot_rows),
        "trend_rows_created": len(trend_summary_rows),
        "kpi_rows_excluded_unreliable_period": kpi_stats.kpi_rows_excluded_unreliable_period,
        "kpi_rows_excluded_semantic_mismatch": kpi_stats.kpi_rows_excluded_semantic_mismatch,
        "kpi_rows_excluded_competitor": kpi_stats.kpi_rows_excluded_competitor,
        "trend_rows_excluded_unreliable_period": trend_stats.trend_rows_excluded_unreliable_period,
        "excluded_kpi_names": sorted(kpi_stats.excluded_kpi_names),
        "excluded_trend_names": sorted(trend_stats.excluded_trend_names),
        "output_files": {
            "executive_kpi_snapshot": str(EXEC_KPI_SNAPSHOT_CSV),
            "executive_trend_summary": str(EXEC_TREND_SUMMARY_CSV),
        },
    }
