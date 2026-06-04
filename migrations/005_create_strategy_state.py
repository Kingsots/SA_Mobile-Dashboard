"""
Migration 005: Create strategy_state table
==========================================

Persistent V2 state machine tracking across Event Monitor sweeps.

Schema stores complete SequenceState dataclass as individual columns
to enable SQL queries and direct database inspection.

Handles both bull and bear setups simultaneously:
  - Bull: extreme_visited → break_bar → retest_done → entry_window_armed
  - Bear: extreme_visited → break_bar → retest_done → entry_window_armed

Added 2026-02-27 to support persistent V2 lifecycle state.
"""

import sqlite3
from pathlib import Path

try:
    from core.config import Config
except Exception:
    Config = None

DEFAULT_DB_PATH = Path("trading_bot.db")


def _resolve_db_path(db_path=None) -> Path:
    if db_path:
        return Path(db_path)
    if Config is not None and getattr(Config, "DB_PATH", None):
        return Path(Config.DB_PATH)
    return DEFAULT_DB_PATH


def run_migration(db_path=None):
    """
    Create strategy_state table for V2 state persistence.
    
    This migration is idempotent (uses CREATE TABLE IF NOT EXISTS).
    
    Args:
        db_path: Path to database file (string or Path object)
    """
    db_file = _resolve_db_path(db_path)
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    
    # Main strategy state table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            
            -- Identity
            ticker TEXT NOT NULL,
            interval TEXT NOT NULL,
            strategy_name TEXT NOT NULL DEFAULT 'strategy_core_v2',
            
            -- Stage 1A: Extreme zone tracking
            bull_extreme_visited INTEGER DEFAULT 0,
            bear_extreme_visited INTEGER DEFAULT 0,
            extreme_bar INTEGER DEFAULT 0,
            
            -- Stage 1B: RSI Break tracking
            bull_break_bar INTEGER,
            bear_break_bar INTEGER,
            
            -- Stage 1C: Retest tracking
            bull_retest_done INTEGER DEFAULT 0,
            bear_retest_done INTEGER DEFAULT 0,
            bull_retest_bar INTEGER,
            bear_retest_bar INTEGER,
            
            -- Stage 2: Entry window tracking
            bull_entry_armed INTEGER DEFAULT 0,
            bear_entry_armed INTEGER DEFAULT 0,
            bull_entry_window_bar INTEGER,
            bear_entry_window_bar INTEGER,
            
            -- Lifecycle management
            last_processed_bar_time TEXT,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
            
            -- Ensure one row per (ticker, interval, strategy) combo
            UNIQUE(ticker, interval, strategy_name)
        )
    ''')
    
    # Index for fast lookups
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_strategy_state_symbol_interval
        ON strategy_state(ticker, interval)
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Migration 005: strategy_state table created")


if __name__ == '__main__':
    # For manual testing
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'trading_bot.db'
    run_migration(db_path)
