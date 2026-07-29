"""
Metric extraction: turn a classified, relevant table into candidate
structured observations.

Approach: the first row is treated as the header row (consistent with
how pdfplumber typically extracts tables in this document). For every
subsequent row, the first non-empty cell is treated as the row label and
matched against the metric keyword registry (src/normalization/
metric_definitions.py). If a row label matches a known metric, every
other cell in that row is checked for a parseable numeric value; each
one becomes a separate candidate observation, with its column header
used to detect a reporting period or geography.

Rows whose label does not match any known metric are skipped entirely -
this module does not invent new metrics from arbitrary table rows.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.normalization.metric_definitions import (
    KNOWN_INDIAN_CITIES,
    METRIC_DEFINITIONS,
    MetricDefinition,
)
from src.normalization.value_parser import ParsedPeriod, ParsedValue, detect_period, parse_numeric_value


@dataclass
class CandidateObservation:
    metric: MetricDefinition
    row_label: str
    column_header: str | None
    raw_value: str
    parsed_value: ParsedValue
    parsed_period: ParsedPeriod | None
    geography: str | None


def _match_metric(row_label: str) -> MetricDefinition | None:
    label_lower = row_label.lower()
    for metric in METRIC_DEFINITIONS:
        for kw in metric.keywords:
            if kw in label_lower:
                return metric
    return None


def _lookup_header(header_row: list, col_idx: int) -> str | None:
    """
    Look up the header value for a data column, tolerating a common
    pdfplumber artifact where merged/spanning header cells shift the
    effective column index by 1-2 positions relative to the data row
    (each row's cell boundaries are detected independently). Prefers the
    exact index, then checks nearby offsets.
    """
    for offset in (0, 1, -1, 2, -2):
        idx = col_idx + offset
        if 0 <= idx < len(header_row) and header_row[idx]:
            return str(header_row[idx]).strip()
    return None


def _detect_geography(header: str | None) -> str | None:
    if not header:
        return None
    lower = header.lower()
    for city in KNOWN_INDIAN_CITIES:
        if city in lower:
            return city.title()
    return None


def _row_label(row: list) -> str | None:
    return next((str(c).strip() for c in row if c not in (None, "")), None)


def _merge_header_block(header_rows: list[list]) -> list[str | None]:
    """
    Many real-world tables split the header across multiple rows AND
    columns (e.g. a company name spanning 10 columns on row 0, with
    "2025"/"2024"/"2023" sub-headers one row below within that span - a
    two-dimensional "company block x year sub-block" header, as seen in
    peer-comparison tables). This:

    1. Forward-fills each header row left-to-right, so a spanning header
       cell (followed by blank cells that are really a continuation of
       it in the source PDF) is carried across the columns it visually
       spans.
    2. Concatenates the distinct forward-filled values from every header
       row for each column, so a single column's header context can
       contain BOTH the company name AND the year (e.g. "Awfis Space
       Solutions Limited | 2025") - which lets period detection and
       competitor-brand detection both work off the same context string.

    This is a heuristic, not a full table-structure parser: in complex
    nested headers, forward-fill carry-over can occasionally bleed a
    label one column past its true boundary. Documented as a known
    limitation rather than silently assumed perfect.
    """
    if not header_rows:
        return []
    width = max(len(r) for r in header_rows)

    filled_rows: list[list[str | None]] = []
    for row in header_rows:
        filled: list[str | None] = []
        last = None
        for i in range(width):
            cell = row[i] if i < len(row) else None
            if cell not in (None, ""):
                last = str(cell).strip()
            filled.append(last)
        filled_rows.append(filled)

    merged: list[str | None] = []
    for col in range(width):
        parts: list[str] = []
        for filled in filled_rows:
            val = filled[col]
            if val and val not in parts:
                parts.append(val)
        merged.append(" | ".join(parts) if parts else None)
    return merged


def extract_observations(rows: list[list]) -> list[CandidateObservation]:
    """Extract candidate metric observations from one already-classified table."""
    if len(rows) < 2:
        return []

    # Find the first row whose label matches a known metric - everything
    # before it is treated as (possibly multi-row) header.
    first_data_idx = None
    for i, row in enumerate(rows):
        label = _row_label(row)
        if label and _match_metric(label) is not None:
            first_data_idx = i
            break

    if first_data_idx is None or first_data_idx == 0:
        return []

    header_row = _merge_header_block(rows[:first_data_idx])
    candidates: list[CandidateObservation] = []

    for row in rows[first_data_idx:]:
        if not row:
            continue
        row_label = _row_label(row)
        if not row_label:
            continue

        metric = _match_metric(row_label)
        if metric is None:
            continue

        for col_idx, cell in enumerate(row):
            if cell is None or str(cell).strip() == "" or str(cell).strip() == row_label:
                continue

            # Percentage-typed metrics must show an explicit "%" in the
            # source cell. A row can legitimately hold both an absolute
            # figure (e.g. revenue) and a percentage in different columns
            # (e.g. "Top 10 Clients" -> revenue AND % of revenue); without
            # this check the absolute figure would be wrongly mislabeled
            # as the percentage.
            default_unit = None if metric.unit == "%" else (metric.unit if metric.unit != "count" else None)
            parsed = parse_numeric_value(cell, table_default_unit=default_unit)
            if parsed is None:
                continue
            if metric.unit == "%" and parsed.standardized_unit != "%":
                continue
            # Symmetric guard: a row label can ambiguously match a
            # non-percentage metric (e.g. "...loss for the year..." also
            # matching a "...as a percentage of Total Income" row) - a
            # cell that is explicitly a percentage should never be
            # accepted as the value for a currency/count metric.
            if metric.unit != "%" and parsed.standardized_unit == "%":
                continue

            column_header = _lookup_header(header_row, col_idx)

            candidates.append(
                CandidateObservation(
                    metric=metric,
                    row_label=row_label,
                    column_header=column_header,
                    raw_value=str(cell).strip(),
                    parsed_value=parsed,
                    parsed_period=detect_period(column_header),
                    geography=_detect_geography(column_header),
                )
            )

    return candidates
