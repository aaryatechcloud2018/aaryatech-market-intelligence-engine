"""
Tests for the database schema (Phase 2).

These tests only verify that the schema can be created and contains the
expected dimension and fact tables. Pipeline behavior (ingestion,
extraction, analytics, etc.) is tested separately once those modules
exist.
"""

from __future__ import annotations

from sqlalchemy import inspect

from src.db.schema import all_table_names, create_all_tables, get_engine

EXPECTED_DIMENSION_TABLES = {
    "dim_project",
    "dim_company",
    "dim_competitor",
    "dim_geography",
    "dim_date",
    "dim_metric",
    "dim_source",
    "dim_document",
    "dim_entity",
}

EXPECTED_FACT_TABLES = {
    "fact_document_text",
    "fact_extracted_table",
    "fact_observation",
    "fact_company_metric",
    "fact_market_metric",
    "fact_competitor_metric",
    "fact_hypothesis_test",
    "fact_insight",
    "fact_market_gap",
    "fact_recommendation",
}


def test_all_tables_created_in_memory():
    engine = get_engine(":memory:")
    create_all_tables(engine)

    inspector = inspect(engine)
    actual_tables = set(inspector.get_table_names())

    missing = (EXPECTED_DIMENSION_TABLES | EXPECTED_FACT_TABLES) - actual_tables
    assert not missing, f"Missing expected tables: {missing}"


def test_all_table_names_matches_expected_set():
    names = set(all_table_names())
    assert EXPECTED_DIMENSION_TABLES.issubset(names)
    assert EXPECTED_FACT_TABLES.issubset(names)


def test_dim_metric_primary_key_is_string_id():
    engine = get_engine(":memory:")
    create_all_tables(engine)
    inspector = inspect(engine)

    pk = inspector.get_pk_constraint("dim_metric")
    assert pk["constrained_columns"] == ["metric_id"]
