"""Test each detector independently"""

import sqlite3
import pandas as pd
from signals.market_structure import detect_higher_high_breakout, detect_lower_low_breakdown
from signals.momentum_confirmation import detect_rsi_shift
from signals.volume_volatility import detect_volume_spike

# Load 1h data
db = sqlite3.connect('trading_bot.db')
query = """
SELECT timestamp, open, high, low, close, volume 
FROM ohlcv_data 
WHERE symbol = 'EURUSD' AND timeframe = '1h'
ORDER BY timestamp DESC 
LIMIT 250
"""
df_raw = pd.read_sql_query(query, db)
db.close()

df = df_raw.iloc[::-1].reset_index(drop=True)

print(f"Data shape: {df.shape}")
print(f"Date range: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
print()

# Test each old detector
print("Testing OLD detectors:")
print("-" * 60)

print("\n1. Higher High Breakout (lookback=20, min_break_ratio=0.0005):")
event = detect_higher_high_breakout(df, lookback=20, min_break_ratio=0.0005)
print(f"   Result: {event}")
if event:
    print(f"   Type: {event.event_type}, Confidence: {event.confidence}")

print("\n2. Lower Low Breakdown (lookback=20, min_break_ratio=0.0005):")
event = detect_lower_low_breakdown(df, lookback=20, min_break_ratio=0.0005)
print(f"   Result: {event}")
if event:
    print(f"   Type: {event.event_type}, Confidence: {event.confidence}")

print("\n3. RSI Shift (period=14):")
event = detect_rsi_shift(df, period=14)
print(f"   Result: {event}")
if event:
    print(f"   Type: {event.event_type}, Confidence: {event.confidence}")

print("\n4. Volume Spike (window=20):")
event = detect_volume_spike(df, window=20)
print(f"   Result: {event}")
if event:
    print(f"   Type: {event.event_type}, Confidence: {event.confidence}")

print("\n" + "=" * 60)
print("Debug: DataFrame info")
print("=" * 60)
print(f"Shape: {df.shape}")
print(f"Columns: {df.columns.tolist()}")
print(f"Close range: {df['close'].min()} to {df['close'].max()}")
print(f"Volume: all zeros? {(df['volume'] == 0).all()}")
