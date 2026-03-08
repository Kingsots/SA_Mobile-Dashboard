#!/usr/bin/env python3
"""Clean old signals from database before hybrid mode deployment."""

import sqlite3
from datetime import datetime

db_path = 'trading_bot.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Get count before
c.execute("SELECT COUNT(*) FROM ml_signals")
total_before = c.fetchone()[0]

# Delete signals before Dec 23, 2025 12:00 UTC (deployment time)
cutoff_date = '2025-12-23 12:00:00'
c.execute(f"DELETE FROM ml_signals WHERE timestamp < '{cutoff_date}'")
deleted_count = c.rowcount

conn.commit()

# Get count after
c.execute("SELECT COUNT(*) FROM ml_signals")
total_after = c.fetchone()[0]

# Get latest signal
c.execute("SELECT MAX(timestamp), COUNT(*) FROM ml_signals")
latest_row = c.fetchone()
latest_timestamp = latest_row[0]

print(f"=" * 70)
print(f"  🧹 SIGNAL DATABASE CLEANUP")
print(f"=" * 70)
print(f"\n  Cutoff Date: {cutoff_date} UTC")
print(f"  Signals deleted: {deleted_count}")
print(f"  Total before: {total_before}")
print(f"  Total after: {total_after}")
if latest_timestamp:
    print(f"  Latest signal: {latest_timestamp}")
else:
    print(f"  Latest signal: (none)")

print(f"\n✅ Database cleaned!")
print(f"=" * 70)

conn.close()
