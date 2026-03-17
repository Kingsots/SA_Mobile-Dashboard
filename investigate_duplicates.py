#!/usr/bin/env python3
"""
Investigate duplicate API calls in apiusage log
"""
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict

db_path = '/home/ubuntu/SilentAnalyst/trading_bot.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all API calls from last 10 minutes, grouped by symbol/interval
cursor.execute("""
    SELECT id, timestamp, ticker, interval, success, error_message 
    FROM api_usage 
    WHERE api_name = 'tiingo' 
    AND timestamp >= datetime('now', '-10 minutes')
    ORDER BY ticker, interval, timestamp DESC
""")

rows = cursor.fetchall()

print("=" * 100)
print("API USAGE PATTERN ANALYSIS")
print("=" * 100)

# Group by symbol-interval pair
calls_by_symbol = defaultdict(list)
for row in rows:
    call_id, ts, ticker, interval, success, error = row
    key = f"{ticker}-{interval}"
    calls_by_symbol[key].append((call_id, ts, success, error))

# Analyze duplicates
print("\n📊 CALL FREQUENCY BY SYMBOL-INTERVAL:")
print("-" * 100)
print(f"{'Symbol-Interval':<20} {'Count':<8} {'First Call':<35} {'Last Call':<35}")
print("-" * 100)

for key in sorted(calls_by_symbol.keys()):
    calls = calls_by_symbol[key]
    first_ts = calls[-1][1]  # Last in list is oldest
    last_ts = calls[0][1]    # First in list is newest
    
    status = "✅ NORMAL (1 call)" if len(calls) == 1 else f"⚠️  DUPLICATE ({len(calls)} calls)"
    
    print(f"{key:<20} {len(calls):<8} {first_ts:<35} {last_ts:<35}")
    
    # If duplicates, show the time delta
    if len(calls) > 1:
        t1 = datetime.fromisoformat(calls[-1][1])
        t2 = datetime.fromisoformat(calls[0][1])
        delta_ms = (t2 - t1).total_seconds() * 1000
        print(f"  └─ Time delta: {delta_ms:.0f}ms between {len(calls)} calls")
        
        # Show each call
        for i, (call_id, ts, success, error) in enumerate(calls):
            status_str = "✅" if success else "❌"
            print(f"     [{i+1}] {status_str} {ts} (ID:{call_id}) {error or ''}")

print("\n" + "=" * 100)
print("FINAL DIAGNOSIS")
print("=" * 100)

# Count duplicates
duplicate_keys = [k for k, v in calls_by_symbol.items() if len(v) > 1]
total_calls = sum(len(v) for v in calls_by_symbol.values())
expected_calls = len(calls_by_symbol)

print(f"\nTotal Unique Symbol-Intervals: {len(calls_by_symbol)}")
print(f"Total API Calls Made: {total_calls}")
print(f"Expected Calls (1 per symbol): {expected_calls}")
print(f"EXTRA CALLS: {total_calls - expected_calls}")
print(f"Duplicate Symbol-Intervals: {len(duplicate_keys)}")

if duplicate_keys:
    print(f"\n⚠️  Symbols with duplicates: {', '.join(duplicate_keys[:5])}")

conn.close()
