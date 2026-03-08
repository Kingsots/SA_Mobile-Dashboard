#!/usr/bin/env python3
import sqlite3
import sys

# Query EC2 database via SSH (will be copied and run)
db_path = "/home/ubuntu/opticore-bot/trading_bot.db"

try:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Total count
    c.execute("SELECT COUNT() FROM ml_signals")
    total = c.fetchone()[0]
    print(f"✅ Total signals in EC2 DB: {total}")
    
    # Latest signals
    print("\nLatest 20 signals (timestamp | ticker | signal | confidence):")
    print("-" * 70)
    c.execute("SELECT timestamp, ticker, signal, confidence FROM ml_signals ORDER BY timestamp DESC LIMIT 20")
    for row in c.fetchall():
        print(f"{row[0]} | {row[1]:12} | {row[2]:+3} | {row[3]:.1f}")
    
    conn.close()
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
