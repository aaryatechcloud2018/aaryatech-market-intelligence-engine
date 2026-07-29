"""
Analytics catalog (Phase 4, Step 7) - the provenance layer describing
every metric that appears in the Gold-layer Power BI outputs.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from src.analytics.kpi_builder import KpiRow


@dataclass
class CatalogEntry:
    metric_name: str
    definition: str
    calculation_method: str
    unit: str | None
    source_observation_ids: list[int]
    source_document: str
    source_page: list[int]
    confidence: float | None
    analysis_status: str  # DIRECTLY_EXTRACTED / DERIVED


def build_analytics_catalog(kpi_rows: list[KpiRow]) -> list[CatalogEntry]:
    groups: dict[str, list[KpiRow]] = defaultdict(list)
    for row in kpi_rows:
        groups[row.kpi_name].append(row)

    entries: list[CatalogEntry] = []
    for kpi_name, rows in sorted(groups.items()):
        is_derived = kpi_name.endswith(" Growth")
        confidences = [r.confidence for r in rows if r.confidence is not None]

        if is_derived:
            base_metric = kpi_name[: -len(" Growth")]
            definition = f"Percentage change in {base_metric} between the earliest and latest available reporting periods for the same entity."
            calculation_method = "percentage_change = (ending_value - starting_value) / abs(starting_value) * 100"
            status = "DERIVED"
        else:
            definition = f"{kpi_name} as directly reported in the source document."
            calculation_method = "Extracted directly from a source table cell; normalized for units/percentages (Phase 2)."
            status = "DIRECTLY_EXTRACTED"

        entries.append(
            CatalogEntry(
                metric_name=kpi_name,
                definition=definition,
                calculation_method=calculation_method,
                unit=rows[0].unit,
                source_observation_ids=sorted({r.source_observation_id for r in rows}),
                source_document=rows[0].source_document,
                source_page=sorted({r.page_number for r in rows if r.page_number is not None}),
                confidence=round(sum(confidences) / len(confidences), 3) if confidences else None,
                analysis_status=status,
            )
        )
    return entries
