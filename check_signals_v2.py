#!/usr/bin/env python3
import sqlite3

db = sqlite3.connect('/home/ubuntu/SilentAnalyst/trading_bot.db')
cursor = db.cursor()

# Get ml_signals schema
cursor.execute("PRAGMA table_info(ml_signals)")
cols = cursor.fetchall()
print("ml_signals columns:")
for col in cols:
    print(f"  {col[1]}: {col[2]}")

# Count by model_version
cursor.execute("SELECT model_version, COUNT(*) FROM ml_signals GROUP BY model_version")
print("\nSignals by model_version:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}")

# Show recent signals
cursor.execute("SELECT ticker, interval, timestamp, signal, model_version FROM ml_signals ORDER BY timestamp DESC LIMIT 5")
print(f"\nRecent signals:")
for row in cursor.fetchall():
    print(f"  {row}")

db.close()
