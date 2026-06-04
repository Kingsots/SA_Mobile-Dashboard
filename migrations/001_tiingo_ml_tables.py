"""
Database Migration for Tiingo + ML Pipeline
Creates new tables required for the upgrade.
"""

import sqlite3
from pathlib import Path

try:
    from core.config import Config  # type: ignore
except Exception:  # pragma: no cover - fallback when Config unavailable
    Config = None

DEFAULT_DB_PATH = Path("trading_bot.db")


def _resolve_db_path(db_path=None) -> Path:
    if db_path:
        return Path(db_path)
    if Config is not None and getattr(Config, "DB_PATH", None):
        return Path(Config.DB_PATH)
    return DEFAULT_DB_PATH


def run_migration(db_path=None):
    """Execute database schema migrations"""
    db_file = _resolve_db_path(db_path)
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    
    print("=" * 70)
    print("  🔄 DATABASE MIGRATION - Tiingo + ML Pipeline")
    print("=" * 70)
    print()
    
    # 1. DEPRECATED: ohlcv_raw table (replaced by ohlcv_data via migration 003)
    # This table is no longer created - all OHLCV data uses ohlcv_data table
    # with symbol/timeframe columns (see migration 003)
    print("1️⃣  Skipping ohlcv_raw creation (deprecated - use ohlcv_data instead)")
    
    # 2. Create features table
    print("\n2️⃣  Creating features table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS features (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            ticker TEXT NOT NULL,
            interval TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            ema_21 REAL,
            ema_100 REAL,
            rsi_14 REAL,
            obv REAL,
            ad REAL,
            vwap REAL,
            vwap_slope REAL,
            volume_sma_20 REAL,
            volume_ratio REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, interval, timestamp)
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_features_ticker_interval 
        ON features(ticker, interval)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_features_timestamp 
        ON features(timestamp)
    """)
    print("   ✅ features table created")
    
    # 3. Create signals table (ML predictions)
    print("\n3️⃣  Creating ml_signals table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ml_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            ticker TEXT NOT NULL,
            interval TEXT NOT NULL,
            signal INTEGER NOT NULL,
            confidence REAL,
            feature_snapshot TEXT,
            model_version TEXT,
            triggered_by TEXT DEFAULT 'time',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ml_signals_ticker 
        ON ml_signals(ticker)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ml_signals_timestamp 
        ON ml_signals(timestamp)
    """)
    print("   ✅ ml_signals table created")
    
    # 4. Create API usage tracking table
    print("\n4️⃣  Creating api_usage table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            api_name TEXT NOT NULL,
            endpoint TEXT,
            ticker TEXT,
            interval TEXT,
            success INTEGER DEFAULT 1,
            error_message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_api_usage_timestamp 
        ON api_usage(timestamp)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_api_usage_api_name 
        ON api_usage(api_name)
    """)
    print("   ✅ api_usage table created")
    
    # 5. Create model training log table
    print("\n5️⃣  Creating model_training_log table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS model_training_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            model_version TEXT NOT NULL,
            train_samples INTEGER,
            test_samples INTEGER,
            accuracy REAL,
            precision_score REAL,
            recall REAL,
            f1_score REAL,
            training_time_seconds REAL,
            deployed INTEGER DEFAULT 0,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_model_log_timestamp 
        ON model_training_log(timestamp)
    """)
    print("   ✅ model_training_log table created")
    
    # 6. Create rate limit tracking table
    print("\n6️⃣  Creating rate_limits table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rate_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_name TEXT NOT NULL,
            period TEXT NOT NULL,
            request_count INTEGER DEFAULT 0,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("   ✅ rate_limits table created")
    
    conn.commit()
    
    # Verify tables
    print("\n7️⃣  Verifying tables...")
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' 
        ORDER BY name
    """)
    tables = [row[0] for row in cursor.fetchall()]
    
    required_tables = [
        'features', 
        'ml_signals', 
        'api_usage',
        'model_training_log',
        'rate_limits'
    ]
    
    for table in required_tables:
        if table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"   ✅ {table:25} ({count} records)")
        else:
            print(f"   ❌ {table:25} MISSING!")
    
    conn.close()
    
    print()
    print("=" * 70)
    print("  ✅ MIGRATION COMPLETE")
    print("=" * 70)
    print()

if __name__ == '__main__':
    run_migration()
