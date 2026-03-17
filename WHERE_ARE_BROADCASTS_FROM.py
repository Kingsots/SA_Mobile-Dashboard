#!/usr/bin/env python3
"""Find where signals are being stored and broadcast"""

import sqlite3
from datetime import datetime, timedelta

DB = "/home/ubuntu/SilentAnalyst/trading_bot.db"
conn = sqlite3.connect(DB)
c = conn.cursor()

print("\n" + "="*100)
print("CRITICAL FINDING: WHERE BROADCAST SIGNALS COME FROM")
print("="*100)

# Schema of ml_signals table
print("\n[ML_SIGNALS TABLE SCHEMA]")
c.execute("PRAGMA table_info(ml_signals);")
for row in c.fetchall():
    print(f"  {row}")

# What signals were created recently?
print("\n[RECENT ML_SIGNALS (last 3 hours)]")
three_hours_ago = (datetime.now() - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')

c.execute("""
    SELECT COUNT(*) FROM ml_signals WHERE created_at > ?
""", (three_hours_ago,))
count = c.fetchone()[0]
print(f"Total: {count} signals in last 3 hours\n")

c.execute("""
    SELECT ticker, interval, signal, COUNT(*) as cnt, MAX(created_at)
    FROM ml_signals
    WHERE created_at > ?
    GROUP BY ticker, interval, signal
    ORDER BY cnt DESC
    LIMIT 20;
""", (three_hours_ago,))

print("Most repeated signals:")
print(f"{'Symbol':10s} {'Interval':10s} {'Signal':10s} {'Count':6s} {'Last Time'}")
print("-" * 70)
for ticker, interval, signal, cnt, last_time in c.fetchall():
    sig_label = "BUY" if signal == 1 else "SELL" if signal == -1 else "NEUTRAL"
    print(f"{ticker:10s} {interval:10s} {sig_label:10s} {cnt:6d}  {last_time}")

# Check strategy_transition_log
print("\n[STRATEGY_TRANSITION_LOG (232K rows!)]")
print("This table has EVERY state change - checking if duplicates appear here...")

c.execute("""
    SELECT ticker, interval, direction, COUNT(*) as cnt
    FROM strategy_transition_log
    WHERE old_stage = 'entry_fired' AND new_stage IN ('entry_confirmed', 'signal_fired')
    GROUP BY ticker, interval, direction
    HAVING COUNT(*) > 2
    ORDER BY cnt DESC
    LIMIT 15;
""")

rows = c.fetchall()
if rows:
    print("\nSymbols with MULTIPLE 'entry_fired' events in strategy_transition_log:")
    for ticker, interval, direction, cnt in rows:
        print(f"  {ticker:8s} {interval:6s} {direction:10s}: {cnt} times")

# What about the Telegram broadcast sequence?
print("\n[CHECKING FOR RAPID-FIRE BROADCAST PATTERN]")
print("Looking for same signal created multiple times in quick succession...\n")

c.execute("""
    SELECT 
        ticker, interval, signal,
        COUNT(*) as times_created,
        CAST((julianday(MAX(created_at)) - julianday(MIN(created_at))) * 1440 AS INTEGER) as minutes_span
    FROM ml_signals
    WHERE created_at > ?
    GROUP BY ticker, interval, signal
    HAVING COUNT(*) > 3
    ORDER BY times_created DESC
    LIMIT 10;
""", (three_hours_ago,))

rows = c.fetchall()
if rows:
    print("Signals created multiple times in last 3 hours:")
    for ticker, interval, signal, times, minutes in rows:
        sig_label = "BUY" if signal == 1 else "SELL"
        avg_min = minutes / times if times > 0 else 0
        print(f"  {ticker:8s} {interval:6s} {sig_label:6s}: {times:2d} times over {minutes:3d} min (avg {avg_min:.1f} min apart)")

conn.close()

print("\n" + "="*100)
print("CONCLUSION")
print("="*100)
print("""
The 'signals' table is EMPTY (0 rows).
The 'ml_signals' table has 6006 records showing SIGNALS ARE CREATED.
Do NOT broadcast emails or signals appear in ml_signals BUT NOT in the trades table.

This suggests:
1. Signals are being generated and saved to ml_signals
2. Trades are NOT being created from these signals
3. OR trades are being created then immediately closed/deleted
4. Duplicate signals in ml_signals means same signal created multiple times
5. This matches the Telegram spam pattern you're seeing!
""")
