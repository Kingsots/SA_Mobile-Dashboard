#!/usr/bin/env python3
"""
Deep Investigation - Understand Signal Duplication Root Cause
Run on EC2: ssh ubuntu@52.90.60.32 'cd /home/ubuntu/SilentAnalyst && python ../../INVESTIGATION_DIAGNOSTIC.py'
"""

import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta

DB = "/home/ubuntu/SilentAnalyst/trading_bot.db"

print("\n" + "="*80)
print("DEEP INVESTIGATION: WHY ARE SIGNALS REPEATING?")
print("="*80)

# ============================================================================
# 1. Check database size and recent activity
# ============================================================================
conn = sqlite3.connect(DB)
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [row[0] for row in c.fetchall()]
print(f"\n📊 DATABASE TABLES: {tables}")

# Count trades total
c.execute("SELECT COUNT(*) FROM trades;")
total_trades = c.fetchone()[0]
print(f"\n📈 Total trades in database: {total_trades}")

# ============================================================================
# 2. Find EXACT DUPLICATE TRADES (same symbol, interval, direction, entry_price)
# ============================================================================
print(f"\n🔍 SEARCHING FOR EXACT DUPLICATE TRADES...")
c.execute("""
    SELECT symbol, interval, direction, entry_price, COUNT(*) as cnt, 
           MIN(created_at) as first_time, MAX(created_at) as last_time
    FROM trades 
    GROUP BY symbol, interval, direction, entry_price
    HAVING COUNT(*) > 1
    ORDER BY cnt DESC
    LIMIT 20;
""")

duplicates = c.fetchall()
if duplicates:
    print(f"\n⚠️  FOUND {len(duplicates)} DUPLICATE SIGNATURES:")
    for row in duplicates:
        sym, interval, direction, price, count, first_time, last_time = row
        print(f"   {sym} {interval} {direction} @ {price:.4f}")
        print(f"      → {count} trades | First: {first_time} | Last: {last_time}")
        
        # Show all trades with this signature
        c.execute("""
            SELECT trade_id, status, created_at FROM trades
            WHERE symbol = ? AND interval = ? AND direction = ? AND entry_price = ?
            ORDER BY created_at;
        """, (sym, interval, direction, price))
        subtrades = c.fetchall()
        for tid, status, ctime in subtrades:
            print(f"      • {tid[:12]} ({status}) @ {ctime}")
else:
    print("\n✅ No exact duplicates found (by symbol-interval-direction-entry_price)")

# ============================================================================
# 3. Check ACTIVE vs CLOSED trades
# ============================================================================
print(f"\n🎯 TRADE STATUS BREAKDOWN:")
c.execute("SELECT status, COUNT(*) FROM trades GROUP BY status;")
for status, count in c.fetchall():
    print(f"   {status}: {count}")

# ============================================================================
# 4. Check if same trades keep being created (time-based duplicates)
# ============================================================================
print(f"\n⏱️  SAME TRADE SIGNALS REPEATED OVER TIME:")
c.execute("""
    SELECT symbol, interval, direction, entry_price, COUNT(*) as times_created,
           CAST((julianday(MAX(created_at)) - julianday(MIN(created_at))) * 1440 AS INTEGER) as minutes_apart
    FROM trades
    WHERE status = 'ACTIVE' OR status = 'PENDING'
    GROUP BY symbol, interval, direction, entry_price
    HAVING COUNT(*) > 1
    ORDER BY times_created DESC
    LIMIT 10;
""")

active_dupes = c.fetchall()
if active_dupes:
    print(f"\n⚠️  ACTIVE TRADES WITH MULTIPLE CREATIONS:")
    for row in active_dupes:
        sym, interval, direction, price, times, minutes = row
        print(f"   {sym} {interval} {direction} @ {price:.4f}")
        print(f"      → Created {times} times over {minutes} minutes ({minutes//times if times else 0} min apart)")
else:
    print("   ✅ No active/pending duplicates")

# ============================================================================
# 5. Check recent trades (last 2 hours)
# ============================================================================
print(f"\n📅 RECENT TRADES (last 2 hours):")
two_hours_ago = (datetime.now() - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
c.execute("""
    SELECT symbol, interval, direction, entry_price, status, created_at
    FROM trades
    WHERE created_at > ?
    ORDER BY created_at DESC
    LIMIT 30;
""", (two_hours_ago,))

recent = c.fetchall()
print(f"   Found {len(recent)} recent trades")

# Group by signature to see repeats
from collections import Counter
signatures = [f"{r[0]}-{r[1]}-{r[2]}" for r in recent]
sig_counts = Counter(signatures)
most_repeated = sig_counts.most_common(5)
print(f"\n   MOST REPEATED RECENTLY:")
for sig, count in most_repeated:
    if count > 1:
        print(f"   {sig}: appeared {count} times")

# ============================================================================
# 6. Check scan frequency (by looking at created_at timestamps)
# ============================================================================
print(f"\n📊 SCAN FREQUENCY ANALYSIS (last 10 trades):")
c.execute("SELECT created_at FROM trades ORDER BY created_at DESC LIMIT 10;")
times = [datetime.fromisoformat(row[0]) for row in c.fetchall()]
if len(times) > 1:
    intervals = []
    for i in range(len(times)-1):
        delta = (times[i] - times[i+1]).total_seconds()
        intervals.append(delta)
    avg_interval = sum(intervals) / len(intervals) if intervals else 0
    print(f"   Average seconds between signals: {avg_interval:.1f}s")
    print(f"   Min: {min(intervals):.1f}s, Max: {max(intervals):.1f}s")

conn.close()

print("\n" + "="*80)
print("END INVESTIGATION")
print("="*80 + "\n")
