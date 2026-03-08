#!/usr/bin/env python3
"""Quick test of load_raw_ohlcv after fix."""

from core.database import DatabaseManager

db = DatabaseManager()
print("Testing load_raw_ohlcv for EURUSD...")
try:
    df = db.load_raw_ohlcv('EURUSD', '1h', days=5)
    if df is not None:
        print(f"✅ Success! Shape: {df.shape}")
        print(f"Columns: {df.columns.tolist()}")
        print(df.head())
    else:
        print("❌ Returned None")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
