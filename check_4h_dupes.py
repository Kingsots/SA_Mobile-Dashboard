#!/usr/bin/env python3
import sqlite3
from collections import defaultdict

DB = "/home/ubuntu/SilentAnalyst/trading_bot.db"
conn = sqlite3.connect(DB)
c = conn.cursor()

# Get all 4h API calls grouped by symbol
c.execute('SELECT ticker, COUNT(*) FROM api_usage WHERE interval="4h" AND success=1 GROUP BY ticker ORDER BY ticker')

print("\n4h API CALL COUNTS (All time)")
print("=" * 60)

total = 0
duplicates = {}
for ticker, count in c.fetchall():
    print(f"{ticker:10} : {count} calls")
    total += count
    if count > 1:
        duplicates[ticker] = count

print("=" * 60)
print(f"Total: {total} calls")
print(f"Expected: 12 calls (1 per symbol)")
print(f"Duplicate count: {sum(duplicates.values()) - len(duplicates)} extra calls")
print()

if duplicates:
    print("SYMBOLS WITH DUPLICATES:")
    for ticker in sorted(duplicates.keys()):
        count = duplicates[ticker]
        print(f"  {ticker}: {count} calls ({count-1} duplicates)")
else:
    print("✅ NO DUPLICATES FOUND")

# Now check how many UNIQUE combinations of (ticker, timestamp) exist vs total records
print("\n" + "=" * 60)
print("CHECKING FOR EXACT TIMESTAMP DUPLICATES")
print("=" * 60)

c.execute('''
    SELECT COUNT(*) as total,
           COUNT(DISTINCT ticker, timestamp) as unique_combos
    FROM api_usage 
    WHERE interval = "4h" AND success = 1
''')

total, unique = c.fetchone()
print(f"Total 4h rows: {total}")
print(f"Unique (ticker, timestamp) combinations: {unique}")

if total > unique:
    print(f"⚠️  {total - unique} rows are EXACT DUPLICATES (same ticker + timestamp)")
else:
    print("✅ No exact duplicates")

conn.close()
