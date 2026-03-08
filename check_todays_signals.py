#!/usr/bin/env python3
"""Check signals generated since market open"""
import sqlite3

db = '/home/ubuntu/opticore-bot/trading_bot.db'
conn = sqlite3.connect(db)
cursor = conn.cursor()

# Total signals today
cursor.execute("SELECT COUNT(*) FROM ml_signals WHERE DATE(timestamp) = '2026-01-26'")
total = cursor.fetchone()[0]
print(f"\n📊 SIGNALS GENERATED TODAY (Jan 26): {total}")

if total > 0:
    # By symbol
    cursor.execute("""
    SELECT ticker, COUNT(*) as count 
    FROM ml_signals 
    WHERE DATE(timestamp) = '2026-01-26'
    GROUP BY ticker 
    ORDER BY count DESC 
    LIMIT 10
    """)
    
    print("\nTop Symbols:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} signals")
    
    # Latest signal
    cursor.execute("""
    SELECT timestamp, ticker, signal, confidence 
    FROM ml_signals 
    WHERE DATE(timestamp) = '2026-01-26'
    ORDER BY timestamp DESC 
    LIMIT 1
    """)
    
    latest = cursor.fetchone()
    if latest:
        print(f"\nLatest Signal: {latest[0]} | {latest[1]} | Conf: {latest[3]:.2f}")

else:
    print("  No signals yet (market may have just opened or no events triggered)")

conn.close()
