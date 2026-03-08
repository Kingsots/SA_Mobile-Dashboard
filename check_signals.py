#!/usr/bin/env python3
import sqlite3
import sys
from datetime import datetime

db_path = '/home/ubuntu/opticore-bot/trading_bot.db'

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check recent signals
    print("\n" + "="*60)
    print("RECENT SIGNALS (Last 10)")
    print("="*60)
    cursor.execute('SELECT timestamp, ticker, signal, confidence FROM ml_signals ORDER BY rowid DESC LIMIT 10')
    rows = cursor.fetchall()
    
    if rows:
        for i, row in enumerate(rows, 1):
            timestamp, ticker, signal, confidence = row
            signal_label = "BUY " if signal > 0 else "SELL" if signal < 0 else "NEUTRAL"
            print(f"{i:2d}. {ticker:8s} | {signal_label:6s} | Confidence: {confidence:.1%} | {timestamp}")
    else:
        print("No signals found")
    
    # Check model info
    print("\n" + "="*60)
    print("MODEL METADATA")
    print("="*60)
    cursor.execute('SELECT version, metrics FROM model_training_log ORDER BY timestamp DESC LIMIT 1')
    model_row = cursor.fetchone()
    if model_row:
        print(f"Latest model: {model_row[0]}")
    
    # Count signals by type
    print("\n" + "="*60)
    print("SIGNAL COUNTS (Last 100)")
    print("="*60)
    cursor.execute('SELECT signal, COUNT(*) FROM ml_signals WHERE timestamp > datetime("now", "-1 day") GROUP BY signal')
    counts = cursor.fetchall()
    for signal, count in counts:
        label = "BUY " if signal > 0 else "SELL" if signal < 0 else "NEUTRAL"
        print(f"{label:6s}: {count:4d}")
    
    conn.close()
    print("\n✅ Database query successful\n")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
