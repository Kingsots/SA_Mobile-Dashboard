"""Migrate data from ohlcv_raw to ohlcv_data and drop redundant table."""

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


def _table_exists(cursor: sqlite3.Cursor, table: str) -> bool:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    )
    return cursor.fetchone() is not None


def run_migration(db_path: Optional[Union[str, Path]] = None) -> None:
    """Migrate ohlcv_raw data to ohlcv_data and drop ohlcv_raw table."""
    db_path = _resolve_db_path(db_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if ohlcv_raw table exists
        if not _table_exists(cursor, 'ohlcv_raw'):
            print("✅ ohlcv_raw table does not exist - no migration needed")
            return
        
        # Check if data exists in ohlcv_raw
        cursor.execute("SELECT COUNT(*) FROM ohlcv_raw")
        count = cursor.fetchone()[0]
        
        if count > 0:
            print(f"🔄 Migrating {count} rows from ohlcv_raw to ohlcv_data...")
            
            # Migrate data: ohlcv_raw columns -> ohlcv_data columns
            cursor.execute("""
                INSERT OR IGNORE INTO ohlcv_data 
                (symbol, timeframe, timestamp, open, high, low, close, volume, source)
                SELECT ticker as symbol, interval as timeframe, timestamp, 
                       open, high, low, close, volume, source
                FROM ohlcv_raw
            """)
            
            print(f"   ✅ Migrated {cursor.rowcount} rows")
        
        # Drop the redundant ohlcv_raw table and its indexes
        print("🗑️  Dropping ohlcv_raw table and indexes...")
        cursor.execute("DROP TABLE IF EXISTS ohlcv_raw")
        print("   ✅ ohlcv_raw table dropped")
        
        conn.commit()
        print("✅ Migration completed: ohlcv_raw → ohlcv_data")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    run_migration()
