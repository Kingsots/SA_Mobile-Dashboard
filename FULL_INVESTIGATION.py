#!/usr/bin/env python3
"""
COMPREHENSIVE SIGNAL PIPELINE INVESTIGATION
Traces exact order of operations and identifies where duplication occurs
"""

import sys
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Setup structured logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)-8s - %(message)s'
)
log = logging.getLogger(__name__)

DB_PATH = "/home/ubuntu/SilentAnalyst/trading_bot.db"

print("\n" + "="*100)
print("COMPREHENSIVE SIGNAL PIPELINE INVESTIGATION REPORT")
print("="*100)

# =============================================================================
# 1. CONFIRM DATABASE PATH AND ACCESS
# =============================================================================
print("\n[PHASE 1] DATABASE PATH AND ACCESS")
print("-" * 100)

if not Path(DB_PATH).exists():
    print(f"❌ Database NOT found at: {DB_PATH}")
    sys.exit(1)
else:
    size_mb = Path(DB_PATH).stat().st_size / (1024**2)
    print(f"✅ Database found: {DB_PATH} ({size_mb:.1f} MB)")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# =============================================================================
# 2. SCHEMA ANALYSIS - What tables actually exist
# =============================================================================
print("\n[PHASE 2] DATABASE SCHEMA")
print("-" * 100)

c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = {row[0]: None for row in c.fetchall()}

print(f"Tables found: {len(tables)}")
for table in sorted(tables.keys()):
    c.execute(f"SELECT COUNT(*) FROM {table};")
    count = c.fetchone()[0]
    print(f"  • {table:30s} - {count:6d} rows")

# =============================================================================
# 3. TRADES TABLE STRUCTURE
# =============================================================================
print("\n[PHASE 3] TRADES TABLE SCHEMA")
print("-" * 100)

c.execute("PRAGMA table_info(trades);")
columns = c.fetchall()
for col in columns:
    cid, name, type_, notnull, dflt_val, pk = col
    print(f"  {name:20s} {type_:10s} {'NOT NULL' if notnull else ''}")

# =============================================================================
# 4. TRADES DATA - What's actually in there
# =============================================================================
print("\n[PHASE 4] TRADES TABLE CONTENTS")
print("-" * 100)

c.execute("SELECT COUNT(*) FROM trades;")
total = c.fetchone()[0]
print(f"Total trades in database: {total}")

if total > 0:
    # Show status distribution
    c.execute("SELECT status, COUNT(*) FROM trades GROUP BY status;")
    print("\nStatus distribution:")
    for status, count in c.fetchall():
        print(f"  {status:15s}: {count:3d} trades")
    
    # Show last 10
    print("\nLast 10 trades (most recent first):")
    c.execute("""
        SELECT trade_id, symbol, interval, direction, entry_price, status, created_at 
        FROM trades 
        ORDER BY created_at DESC 
        LIMIT 10
    """)
    for row in c.fetchall():
        trade_id, symbol, interval, direction, entry, status, created = row
        print(f"  {symbol:8s} {interval:4s} {direction:5s} @ {entry:10.4f} [{status:8s}] {created}")
else:
    print("  (no trades in database)")

# =============================================================================
# 5. DUPLICATE ANALYSIS
# =============================================================================
print("\n[PHASE 5] DUPLICATE TRADE ANALYSIS")
print("-" * 100)

# By exact signature
c.execute("""
    SELECT symbol, interval, direction, entry_price, COUNT(*) as cnt
    FROM trades
    GROUP BY symbol, interval, direction, entry_price
    HAVING COUNT(*) > 1
    ORDER BY cnt DESC;
""")
exact_dupes = c.fetchall()
if exact_dupes:
    print(f"Found {len(exact_dupes)} signatures with exact duplicates:")
    for sym, intf, dir, entry, cnt in exact_dupes:
        print(f"  {sym:8s} {intf:4s} {dir:5s} @ {entry:10.4f}: {cnt} trades")
else:
    print("✅ No exact duplicate signatures found")

# =============================================================================
# 6. ACTIVE vs CLOSED ANALYSIS
# =============================================================================
print("\n[PHASE 6] ACTIVE TRADES ANALYSIS")
print("-" * 100)

c.execute("SELECT COUNT(*) FROM trades WHERE status='ACTIVE' OR status='PENDING';")
active_count = c.fetchone()[0]
print(f"Active/Pending trades: {active_count}")

if active_count > 0:
    c.execute("""
        SELECT symbol, interval, direction, entry_price, created_at 
        FROM trades 
        WHERE status='ACTIVE' OR status='PENDING'
        ORDER BY created_at DESC;
    """)
    for row in c.fetchall():
        sym, intf, dir, entry, created = row
        print(f"  {sym:8s} {intf:4s} {dir:5s} @ {entry:10.4f} [{created}]")

# =============================================================================
# 7. SIGNALS TABLE ANALYSIS
# =============================================================================
print("\n[PHASE 7] SIGNALS TABLE")
print("-" * 100)

if 'signals' in tables:
    c.execute("SELECT COUNT(*) FROM signals;")
    sig_count = c.fetchone()[0]
    print(f"Total signals: {sig_count}")
    
    if sig_count > 0:
        c.execute("""
            SELECT symbol, timeframe, signal_type, COUNT(*) as cnt
            FROM signals
            GROUP BY symbol, timeframe, signal_type
            HAVING COUNT(*) > 5
            ORDER BY cnt DESC
            LIMIT 15;
        """)
        rows = c.fetchall()
        if rows:
            print("Most repeated signal combinations (>5):")
            for sym, intf, sigtype, cnt in rows:
                print(f"  {sym:8s} {intf:4s} {sigtype:15s}: {cnt:4d} times")
else:
    print("No signals table")

# =============================================================================
# 8. ML_SIGNALS TABLE
# =============================================================================
print("\n[PHASE 8] ML_SIGNALS TABLE")
print("-" * 100)

if 'ml_signals' in tables:
    c.execute("SELECT COUNT(*) FROM ml_signals;")
    ml_count = c.fetchone()[0]
    print(f"Total ML signals: {ml_count}")
    
    if ml_count > 0:
        two_hours_ago = (datetime.now() - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
        c.execute("""
            SELECT COUNT(*) FROM ml_signals WHERE created_at > ?
        """, (two_hours_ago,))
        recent_count = c.fetchone()[0]
        print(f"Recent ML signals (last 2 hours): {recent_count}")
        
        if recent_count > 0:
            c.execute("""
                SELECT symbol, interval, signal, COUNT(*) as cnt
                FROM ml_signals
                WHERE created_at > ?
                GROUP BY symbol, interval, signal
                ORDER BY cnt DESC
                LIMIT 15;
            """, (two_hours_ago,))
            for sym, intf, sig, cnt in c.fetchall():
                sig_label = 'BUY' if sig == 1 else 'SELL' if sig == -1 else 'NEUTRAL'
                print(f"  {sym:8s} {intf:4s} {sig_label:8s}: {cnt:3d} signals (last 2h)")
else:
    print("No ml_signals table")

# =============================================================================
# 9. SCAN FREQUENCY (estimate from timestamps)
# =============================================================================
print("\n[PHASE 9] PIPELINE TIMING ANALYSIS")
print("-" * 100)

if total > 0:
    c.execute("SELECT created_at FROM trades ORDER BY created_at DESC LIMIT 50;")
    times = [datetime.fromisoformat(row[0]) for row in c.fetchall()]
    
    if len(times) > 1:
        intervals = []
        for i in range(len(times)-1):
            delta = (times[i] - times[i+1]).total_seconds()
            intervals.append(delta)
        
        avg_int = sum(intervals) / len(intervals)
        min_int = min(intervals)
        max_int = max(intervals)
        
        print(f"Trade creation intervals (last 50 trades):")
        print(f"  Average: {avg_int:.2f} seconds")
        print(f"  Minimum: {min_int:.2f} seconds")
        print(f"  Maximum: {max_int:.2f} seconds")
        print(f"  Total samples: {len(intervals)}")
else:
    print("Not enough data for timing analysis")

# =============================================================================
# 10. FIND BROADCAST WITHOUT PERSIST
# =============================================================================
print("\n[PHASE 10] BROADCAST vs PERSISTENCE CHECK")
print("-" * 100)

print("Looking for trades that might be broadcast without being saved...")

# Check if there's a recent Telegram broadcast pattern
two_hours_ago = (datetime.now() - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')

c.execute("SELECT COUNT(*) FROM trades WHERE created_at > ?", (two_hours_ago,))
recent_trades = c.fetchone()[0]
print(f"Trades created in last 2 hours: {recent_trades}")

c.execute("SELECT COUNT(*) FROM ml_signals WHERE created_at > ?", (two_hours_ago,))
recent_signals = c.fetchone()[0]
print(f"ML signals created in last 2 hours: {recent_signals}")

if recent_signals > recent_trades:
    print(f"⚠️  DISCREPANCY: More signals ({recent_signals}) than trades ({recent_trades})")
    print("   This suggests broadcasts might happen WITHOUT database saves!")
else:
    print(f"✅ Signals and trades are roughly aligned: {recent_signals} signals, {recent_trades} trades")

conn.close()

print("\n" + "="*100)
print("END INVESTIGATION")
print("="*100 + "\n")
