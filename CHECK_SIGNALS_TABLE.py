#!/usr/bin/env python3
"""Check the signals table to see what's actually being created"""
import sqlite3
from datetime import datetime, timedelta

DB = "/home/ubuntu/SilentAnalyst/trading_bot.db"
conn = sqlite3.connect(DB)
c = conn.cursor()

print("🔵 SIGNALS TABLE ANALYSIS:")
c.execute("SELECT COUNT(*) FROM signals;")
total_signals = c.fetchone()[0]
print(f"   Total signals: {total_signals}")

# Recent signals
two_hours_ago = (datetime.now() - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
c.execute("""
    SELECT symbol, timeframe, signal_type, COUNT(*) as cnt, 
           MIN(created_at) as first_time, MAX(created_at) as last_time
    FROM signals
    WHERE created_at > ?
    GROUP BY symbol, timeframe, signal_type
    ORDER BY cnt DESC
    LIMIT 20;
""", (two_hours_ago,))

rows = c.fetchall()
if rows:
    print(f"\n   RECENT SIGNALS (last 2 hours): {len(rows)} unique combinations")
    for symbol, timeframe, sig_type, count, first, last in rows[:10]:
        print(f"   {symbol} {timeframe} {sig_type}: {count} times")
        print(f"      First: {first}, Last: {last}")
else:
    print("   No recent signals")

# Check signal_type values
c.execute("SELECT DISTINCT signal_type FROM signals;")
types = [row[0] for row in c.fetchall()]
print(f"\n   Signal types in DB: {types}")

conn.close()
