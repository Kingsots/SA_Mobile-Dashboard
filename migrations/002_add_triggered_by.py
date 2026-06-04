"""Add triggered_by column to ml_signals when missing."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional, Union

try:
    from core.config import Config  # type: ignore
except Exception:  # pragma: no cover
    Config = None

DEFAULT_DB_PATH = Path("trading_bot.db")


def _resolve_db_path(db_path: Optional[Union[str, Path]] = None) -> Path:
    if db_path is not None:
        return Path(db_path)
    if Config is not None and getattr(Config, "DB_PATH", None):
        return Path(Config.DB_PATH)
    return DEFAULT_DB_PATH


def _column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def run_migration(db_path: Optional[Union[str, Path]] = None) -> None:
    """Ensure ml_signals table includes triggered_by metadata column."""
    db_file = _resolve_db_path(db_path)
    conn = sqlite3.connect(str(db_file))
    try:
        cursor = conn.cursor()
        if _column_exists(cursor, "ml_signals", "triggered_by"):
            print("✅ Column 'triggered_by' already present on ml_signals")
            return

        cursor.execute("ALTER TABLE ml_signals ADD COLUMN triggered_by TEXT DEFAULT 'time'")
        conn.commit()
        print("✅ Added 'triggered_by' column to ml_signals")
    finally:
        conn.close()


if __name__ == "__main__":  # pragma: no cover
    run_migration()
