"""
Database initialization.

Creates the SQLite database file (if missing) and all tables defined in
``src.db.schema``. Safe to run multiple times: ``CREATE TABLE IF NOT
EXISTS`` semantics mean existing data is never dropped.
"""

from __future__ import annotations

from pathlib import Path
from sqlalchemy.engine import Engine

from src.config import DATABASE_PATH, ensure_directories
from src.db.schema import all_table_names, create_all_tables, get_engine
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def initialize_database(database_path: Path | str | None = None) -> Engine:
    """Ensure directories exist, then create the DB file and all tables."""
    ensure_directories()

    db_path = Path(database_path) if database_path else DATABASE_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Initializing database at %s", db_path)
    engine = get_engine(str(db_path))
    create_all_tables(engine)

    tables = all_table_names()
    logger.info("Database ready with %d tables: %s", len(tables), ", ".join(tables))
    return engine


if __name__ == "__main__":
    initialize_database()
