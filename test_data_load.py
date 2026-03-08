#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/ubuntu/opticore-bot')
from core.database import DatabaseManager

db = DatabaseManager()
df = db.load_ohlcv_data('XAUUSD', '1h', limit=50)

if df is None:
    print("ERROR: load_ohlcv_data returned None!")
elif df.empty:
    print("ERROR: DataFrame is empty!")
else:
    print(f"SUCCESS: Loaded {len(df)} candles")
    print(f"Columns: {list(df.columns)}")
    print(f"Latest timestamp: {df.iloc[-1]['timestamp']}")
    print(f"\nAttempting detector analysis...")
    
    from signals.market_structure import detect_higher_high_breakout
    result = detect_higher_high_breakout(df, lookback=20, min_break_ratio=0.0005)
    print(f"Higher High Breakout result: {result}")
