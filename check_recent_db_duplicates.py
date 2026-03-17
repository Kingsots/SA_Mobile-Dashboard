#!/usr/bin/env python3
"""
Check if database is also filled with duplicate signals.
"""

import sqlite3
from datetime import datetime, timedelta, timezone

db_path = '/home/ubuntu/SilentAnalyst/trading_bot.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=" * 80)
print("DATABASE DUPLICATE REPLICATION CHECK")
print("=" * 80)

# Get signals from last 2 hours
two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()

query = """
SELECT ticker, interval, signal, COUNT(*) as count, 
       MIN(created_at) as first_seen, MAX(created_at) as last_seen
FROM ml_signals
WHERE created_at >= ?
GROUP BY ticker, interval, signal
ORDER BY count DESC
LIMIT 25
"""

cursor.execute(query, (two_hours_ago,))
results = cursor.fetchall()

print(f"\nSignals from last 2 hours (after {two_hours_ago[:16]} UTC):\n")

total_signals = sum(row['count'] for row in results)
print(f"Total signals in timeframe: {total_signals}\n")

for row in results:
    sig_label = "BUY" if row['signal'] == 1 else ("SELL" if row['signal'] == -1 else "NEUTRAL")
    print(f"{row['ticker']}-{row['interval']} {sig_label:6s}: {row['count']:3d} copies")
    print(f"  First: {row['first_seen']} | Last: {row['last_seen']}")

# Check the exact signals that are being broadcast
print("\n" + "=" * 80)
print("SPECIFIC KNOWN SIGNALS (from 12:35 UTC broadcast)")
print("=" * 80)

known_pairs = [
    ('USDJPY', '4h', -1),  # SELL
    ('USDCAD', '30m', 1),  # BUY
    ('EURJPY', '4h', 1),   # BUY
    ('AUDCAD', '1h', 1),   # BUY
]

for ticker, interval, signal in known_pairs:
    cursor.execute(
        "SELECT COUNT(*) as count FROM ml_signals WHERE ticker=? AND interval=? AND signal=?",
        (ticker, interval, signal)
    )
    count = cursor.fetchone()['count']
    sig_label = "BUY" if signal == 1 else "SELL"
    
    # Also get timestamps of all instances
    cursor.execute(
        "SELECT created_at FROM ml_signals WHERE ticker=? AND interval=? AND signal=? ORDER BY created_at LIMIT 5",
        (ticker, interval, signal)
    )
    timestamps = cursor.fetchall()
    
    print(f"\n{ticker}-{interval} {sig_label}: {count} total copies")
    if timestamps:
        print(f"  Latest 5 timestamps:")
        for ts in timestamps[-5:]:
            print(f"    - {ts['created_at']}")

conn.close()
