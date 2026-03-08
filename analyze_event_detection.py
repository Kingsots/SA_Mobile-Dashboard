#!/usr/bin/env python3
"""Test EventMonitor with relaxed thresholds."""

import sqlite3
import pandas as pd
import numpy as np
from signals.event_monitor import EventMonitor, EventMonitorConfig

db_path = 'trading_bot.db'
conn = sqlite3.connect(db_path)

# Load OHLCV data for EURUSD 1h
query = '''
SELECT timestamp, open, high, low, close, volume 
FROM ohlcv_data 
WHERE symbol = 'EURUSD' AND timeframe = '1h'
ORDER BY timestamp ASC
'''

df = pd.read_sql_query(query, conn)
df['timestamp'] = pd.to_datetime(df['timestamp'])
df.set_index('timestamp', inplace=True)

print("=" * 80)
print("EVENT DETECTION ANALYSIS")
print("=" * 80)
print(f"\nData range: {df.index.min()} to {df.index.max()}")
print(f"Records: {len(df)}\n")

# Analyze price movement
recent = df.tail(250)
print("Price Statistics (last 250 candles):")
print(f"  Close: min={recent['close'].min():.5f}, max={recent['close'].max():.5f}")
print(f"  Range: {(recent['close'].max() - recent['close'].min()):.5f}")
print(f"  Daily change avg: {recent['close'].pct_change().abs().mean():.6f} ({recent['close'].pct_change().abs().mean()*100:.4f}%)")
print(f"  Daily change max: {recent['close'].pct_change().abs().max():.6f} ({recent['close'].pct_change().abs().max()*100:.4f}%)")

# Look for simple structure shifts
print("\nRecent Structure Analysis (last 20 candles):")
tail20 = df.tail(20)
highs = tail20['high'].values
lows = tail20['low'].values
closes = tail20['close'].values

hh_detected = False
ll_detected = False

# Check for higher high
if len(tail20) > 1:
    last_high = tail20['high'].iloc[-1]
    prev_max = tail20['high'].iloc[:-1].max()
    if last_high > prev_max:
        ratio = (last_high - prev_max) / prev_max if prev_max != 0 else 0
        print(f"  Higher High: {last_high:.5f} > {prev_max:.5f} (ratio: {ratio:.6f})")
        hh_detected = ratio > 0.0001

# Check for lower low
if len(tail20) > 1:
    last_low = tail20['low'].iloc[-1]
    prev_min = tail20['low'].iloc[:-1].min()
    if last_low < prev_min:
        ratio = (prev_min - last_low) / prev_min if prev_min != 0 else 0
        print(f"  Lower Low: {last_low:.5f} < {prev_min:.5f} (ratio: {ratio:.6f})")
        ll_detected = ratio > 0.0001

print(f"\nEvent Detection Likelihood:")
print(f"  Higher High potential: {'✅' if hh_detected else '❌'}")
print(f"  Lower Low potential: {'✅' if ll_detected else '❌'}")

# Now test with RELAXED config
print(f"\n" + "=" * 80)
print("TESTING WITH RELAXED THRESHOLDS")
print("=" * 80)

relaxed_config = EventMonitorConfig(
    min_confidence=0.3,  # Lowered from 0.55
    cooldown_seconds=1800,  # Lowered from 3600
    structure_lookback=10,  # Lowered from 20
)

monitor = EventMonitor(relaxed_config)
events = monitor.analyze('EURUSD', '1h', df)

print(f"\nEvents detected (relaxed): {len(events)}")
if events:
    for event in events:
        print(f"  ✅ {event.event_type} (confidence: {event.confidence:.2f})")
else:
    print("  ❌ Still no events detected")

# Try default config
print(f"\n" + "=" * 80)
print("TESTING WITH DEFAULT THRESHOLDS")
print("=" * 80)

default_config = EventMonitorConfig()
monitor2 = EventMonitor(default_config)
events2 = monitor2.analyze('EURUSD', '1h', df)

print(f"\nEvents detected (default): {len(events2)}")
if events2:
    for event in events2:
        print(f"  ✅ {event.event_type} (confidence: {event.confidence:.2f})")
else:
    print("  ❌ No events detected with default config")

conn.close()
print("\n✅ Analysis complete!")
