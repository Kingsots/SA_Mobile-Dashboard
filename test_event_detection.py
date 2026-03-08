#!/usr/bin/env python3
"""Test EventMonitor event detection."""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
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
print("EVENT MONITOR TEST - EURUSD 1h")
print("=" * 80)
print(f"\nLoaded {len(df)} records from {df.index.min()} to {df.index.max()}")
print(f"\nSample data (last 5):")
print(df.tail())

# Initialize EventMonitor
config = EventMonitorConfig()
monitor = EventMonitor(config)

print(f"\n" + "=" * 80)
print("TESTING EVENT DETECTION")
print("=" * 80)

# Test on full dataset
events = monitor.analyze('EURUSD', '1h', df)

print(f"\nTotal events detected: {len(events)}")
if events:
    for event in events:
        print(f"\n  Event Type: {event.event_type}")
        print(f"    Confidence: {event.confidence:.2f}")
        print(f"    Timestamp: {event.timestamp}")
        print(f"    Details: {event.details}")
else:
    print("  ❌ No events detected!")

# Check event monitor stats
stats = monitor.stats()
print(f"\nEvent Monitor Stats:")
for key, value in stats.items():
    print(f"  {key}: {value}")

conn.close()
print("\n✅ Test complete!")
