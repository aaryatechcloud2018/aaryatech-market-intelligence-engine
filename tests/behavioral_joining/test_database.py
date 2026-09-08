import pytest
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.behavioral_joining.database import build_database, DB_PATH

EXPECTED_TABLES = {
    "bj_candidate_journey", "bj_communication_log", "bj_stage_events", "bj_clients",
    "bj_recruiters", "bj_requisitions", "bj_evidence_candidates", "bj_evidence_review",
    "bj_mechanism_reference", "bj_mechanism_mapping_candidates", "bj_mechanism_mapping_review",
    "bj_hypotheses", "bj_statistical_results",
    "bj_evidence_quality", "bj_evidence_review_sample", "bj_mechanism_review",
    "bj_calibration_metrics", "bj_hypothesis_readiness",
}


@pytest.fixture(scope="module")
def db_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "behavioral_joining_test.db"
    build_database(path)
    return path


def test_all_expected_tables_created(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    conn.close()
    assert EXPECTED_TABLES <= tables


def test_all_tables_prefixed_bj(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    conn.close()
    for t in tables:
        assert t.startswith("bj_"), f"table '{t}' is not bj_-prefixed"


def test_indexes_created(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indexes = {r[0] for r in cur.fetchall()}
    conn.close()
    assert "idx_journey_application" in indexes
    assert "idx_evidence_candidates_evidence_id" in indexes
    assert "idx_mapping_candidates_mechanism_id" in indexes


def test_database_file_is_separate_from_repo_main_database():
    """This project's DB file must be distinctly named so it can never collide with
    or overwrite whatever database the existing Market Intelligence Engine uses."""
    assert DB_PATH.name == "behavioral_joining.db"
    assert DB_PATH.name != "database.db"


def test_bj_statistical_results_starts_empty(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM bj_statistical_results")
    count = cur.fetchone()[0]
    conn.close()
    assert count == 0


def test_bj_hypotheses_starts_empty(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM bj_hypotheses")
    count = cur.fetchone()[0]
    conn.close()
    assert count == 0
