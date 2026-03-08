"""
Migration: Add lag1 feature columns to features table
Adds lagged indicator columns for ML model inference
Created: Jan 15, 2026
"""

import sqlite3
from pathlib import Path


def migrate(db_path: str):
    """
    Add lag1 feature columns to features table
    
    Lag1 features are required for XGBoost model inference.
    The model is trained on lagged indicators to prevent lookahead bias.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Lag1 columns to add
    lag1_columns = [
        'ema_21_lag1',
        'ema_100_lag1', 
        'rsi_14_lag1',
        'obv_lag1',
        'ad_lag1',
        'vwap_slope_lag1',
        'volume_sma_20_lag1',
        'volume_ratio_lag1'
    ]
    
    print("📝 Adding lag1 feature columns...")
    
    for col in lag1_columns:
        try:
            cursor.execute(f"ALTER TABLE features ADD COLUMN {col} REAL DEFAULT NULL")
            print(f"   ✅ Added {col}")
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                print(f"   ⚠️  Column {col} already exists")
            else:
                print(f"   ❌ Error adding {col}: {e}")
                raise
    
    conn.commit()
    conn.close()
    
    print("✅ Migration complete - lag1 columns added")


if __name__ == '__main__':
    # For manual testing
    db_path = Path(__file__).parent.parent / 'trading_bot.db'
    migrate(str(db_path))
