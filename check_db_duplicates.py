#!/usr/bin/env python3
"""
Check for duplicate signals in the database.
"""

import sqlite3
import sys

db_path = '/home/ubuntu/SilentAnalyst/trading_bot.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=" * 70)
print("DATABASE DUPLICATE ANALYSIS")
print("=" * 70)

# Total signals
cursor.execute("SELECT COUNT(*) as count FROM ml_signals")
total = cursor.fetchone()['count']
print(f"\n✅ Total signals in database: {total}")

# Check for duplicates - same ticker + interval + signal + timestamp (within same minute)
print("\n" + "=" * 70)
print("CHECKING FOR DUPLICATES (same ticker, interval, signal, timestamp)")
print("=" * 70)

query = """
SELECT 
    ticker, interval, signal, 
    datetime(timestamp) as signal_time,
    COUNT(*) as num_duplicates,
    GROUP_CONCAT(id) as signal_ids
FROM ml_signals
GROUP BY ticker, interval, signal, datetime(timestamp)
HAVING COUNT(*) > 1
ORDER BY num_duplicates DESC
LIMIT 20
"""

cursor.execute(query)
duplicates = cursor.fetchall()

if duplicates:
    print(f"\n⚠️  Found {len(duplicates)} groups with duplicate signals:\n")
    for row in duplicates:
        print(f"  {row['ticker']}-{row['interval']} {row['signal']:+d} @ {row['signal_time']}")
        print(f"    Count: {row['num_duplicates']} | IDs: {row['signal_ids']}")
else:
    print("\n✅ No exact duplicates found (same ticker/interval/signal/timestamp)")

# Check recent signals around 12:35 UTC
print("\n" + "=" * 70)
print("RECENT SIGNALS (12:30 - 12:40 UTC)")
print("=" * 70)

query2 = """
SELECT 
    ticker, interval, signal,
    created_at, id
FROM ml_signals
WHERE created_at >= '2026-03-09 12:30:00' 
  AND created_at <= '2026-03-09 12:40:00'
ORDER BY created_at
"""

cursor.execute(query2)
recent = cursor.fetchall()

print(f"\n{len(recent)} signals in this timeframe:\n")
for row in recent:
    sig_label = "BUY" if row['signal'] == 1 else ("SELL" if row['signal'] == -1 else "NEUTRAL")
    print(f"  {row['created_at']} | {row['ticker']}-{row['interval']} {sig_label:6s} | ID={row['id']}")

# Check if same signals appear multiple times
print("\n" + "=" * 70)
print("DUPLICATE COUNT BY TICKER/INTERVAL/SIGNAL (Last 24h)")
print("=" * 70)

query3 = """
SELECT 
    ticker, interval, signal,
    COUNT(*) as signal_count
FROM ml_signals
WHERE created_at >= datetime('now', '-1 day')
GROUP BY ticker, interval, signal
HAVING COUNT(*) > 5
ORDER BY signal_count DESC
"""

cursor.execute(query3)
high_count = cursor.fetchall()

if high_count:
    print(f"\n⚠️  Signals appearing >5 times in last 24h:\n")
    for row in high_count:
        sig_label = "BUY" if row['signal'] == 1 else ("SELL" if row['signal'] == -1 else "NEUTRAL")
        print(f"  {row['ticker']}-{row['interval']} {sig_label:6s}: {row['signal_count']} times")
else:
    print("\n✅ No excessive duplicates (all ticker/interval/signal combinations ≤5 per day)")

conn.close()
