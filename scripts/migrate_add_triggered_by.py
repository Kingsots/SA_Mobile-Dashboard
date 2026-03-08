"""SQLite migration to add trigger metadata column to ml_signals."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.config import Config


def column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def add_triggered_by_column(connection: sqlite3.Connection) -> None:
    cursor = connection.cursor()
    if column_exists(cursor, "ml_signals", "triggered_by"):
        print("✅ Column 'triggered_by' already exists on ml_signals")
        return

    cursor.execute(
        "ALTER TABLE ml_signals ADD COLUMN triggered_by TEXT DEFAULT 'time'"
    )
    connection.commit()
    print("✅ Added column 'triggered_by' to ml_signals")


def main() -> None:
    db_path = Path(Config.DB_PATH)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}")

    with sqlite3.connect(db_path) as connection:
        add_triggered_by_column(connection)


if __name__ == "__main__":
    main()
