"""
CLI entry point: create the SQLite database and schema.

Usage (from the project root):

    python scripts/init_database.py

This does not touch any input files - it only creates the empty database
structure so it can be inspected before the full pipeline is built.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running this script directly (`python scripts/init_database.py`)
# without having the project installed as a package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DATABASE_PATH
from src.db.init_db import initialize_database
from src.db.schema import all_table_names


def main() -> None:
    print(f"Creating/verifying database at: {DATABASE_PATH}")
    initialize_database()

    tables = all_table_names()
    print(f"\nSuccess. {len(tables)} tables are present:")
    for name in tables:
        print(f"  - {name}")


if __name__ == "__main__":
    main()
