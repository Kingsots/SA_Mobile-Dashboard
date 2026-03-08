#!/usr/bin/env python3
"""Check OHLCV data sample from ohlcv_data table."""

import sqlite3
from datetime import datetime

db_path = 'trading_bot.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Check table structure
print("=" * 80)
print("OHLCV DATA TABLE STRUCTURE")
print("=" * 80)

c.execute("PRAGMA table_info(ohlcv_data)")
for col in c.fetchall():
    print(f"  {col[1]}: {col[2]}")

# Check data counts
print("\n" + "=" * 80)
print("DATA COUNTS BY SYMBOL & TIMEFRAME")
print("=" * 80)

c.execute("SELECT symbol, timeframe, COUNT(*) FROM ohlcv_data GROUP BY symbol, timeframe ORDER BY symbol, timeframe")
for row in c.fetchall():
    print(f"  {row[0]:8} {row[1]:4} -> {row[2]:5} records")

# Check sample data
print("\n" + "=" * 80)
print("SAMPLE DATA (EURUSD 1h - last 5 records)")
print("=" * 80)

c.execute("""
SELECT symbol, timeframe, timestamp, open, high, low, close, volume 
FROM ohlcv_data 
WHERE symbol='EURUSD' AND timeframe='1h'
ORDER BY timestamp DESC
LIMIT 5
""")

for row in c.fetchall():
    print(f"  {row[0]} | {row[1]} | {row[2]} | O:{row[3]:.5f} H:{row[4]:.5f} L:{row[5]:.5f} C:{row[6]:.5f} | V:{row[7]}")

# Check if any records have NULL timestamps or values
print("\n" + "=" * 80)
print("DATA QUALITY CHECK")
print("=" * 80)

c.execute("""
SELECT 
    COUNT(*) as total,
    COUNT(CASE WHEN timestamp IS NULL THEN 1 END) as null_timestamp,
    COUNT(CASE WHEN open IS NULL THEN 1 END) as null_open,
    COUNT(CASE WHEN close IS NULL THEN 1 END) as null_close,
    COUNT(CASE WHEN volume IS NULL THEN 1 END) as null_volume
FROM ohlcv_data
""")

total, null_ts, null_open, null_close, null_vol = c.fetchone()
print(f"  Total records: {total}")
print(f"  Null timestamps: {null_ts}")
print(f"  Null open prices: {null_open}")
print(f"  Null close prices: {null_close}")
print(f"  Null volumes: {null_vol}")

conn.close()
print("\n✅ Check complete!")
