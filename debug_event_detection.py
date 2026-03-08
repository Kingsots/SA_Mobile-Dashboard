"""Debug script to test event detection with actual data"""

import sqlite3
import pandas as pd
from signals.event_monitor import EventMonitor, EventMonitorConfig
from core.config import Config

# Load 1h data for EURUSD
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

# Reverse to chronological order
df = df_raw.iloc[::-1].reset_index(drop=True)

print(f"Loaded {len(df)} rows of EURUSD 1h data")
print(f"Date range: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
print(f"Latest close: {df['close'].iloc[-1]}")
print(f"Volume range: {df['volume'].min()} to {df['volume'].max()}")
print()

# Test event detection
config = EventMonitorConfig()
monitor = EventMonitor(config)

print("=" * 60)
print("Testing Event Detection")
print("=" * 60)

# Test each detector individually
print("\n1. Testing _structure_events()...")
structure_events = monitor._structure_events(df)
print(f"   Found {len(structure_events)} structure events")
for evt in structure_events:
    print(f"   - {evt.event_type}: confidence={evt.confidence}")

print("\n2. Testing _volume_events()...")
volume_events = monitor._volume_events(df)
print(f"   Found {len(volume_events)} volume events")
for evt in volume_events:
    print(f"   - {evt.event_type}: confidence={evt.confidence}")

print("\n3. Testing _momentum_events()...")
momentum_events = monitor._momentum_events(df)
print(f"   Found {len(momentum_events)} momentum events")
for evt in momentum_events:
    print(f"   - {evt.event_type}: confidence={evt.confidence}")

print("\n4. Testing _engulfed_structure_events()...")
engulfed_events = monitor._engulfed_structure_events(df)
print(f"   Found {len(engulfed_events)} engulfed structure events")
for evt in engulfed_events:
    print(f"   - {evt.event_type}: confidence={evt.confidence}")

print("\n5. Testing full analyze()...")
market_events = monitor.analyze('EURUSD', '1h', df)
print(f"   Found {len(market_events)} filtered market events")
for evt in market_events:
    print(f"   - {evt.event_type} (confidence={evt.confidence})")

print("\n" + "=" * 60)
print(f"Total raw events: {len(structure_events) + len(volume_events) + len(momentum_events) + len(engulfed_events)}")
print(f"Total filtered events: {len(market_events)}")
print("=" * 60)
