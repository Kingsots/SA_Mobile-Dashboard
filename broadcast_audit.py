#!/usr/bin/env python3
"""BROADCAST PIPELINE AUDIT — TRACE ONLY (v2)"""
import sqlite3
import subprocess
from datetime import datetime, timezone

db = sqlite3.connect("/home/ubuntu/SilentAnalyst/trading_bot.db")
db.row_factory = sqlite3.Row
cur = db.cursor()

print("\n" + "="*80)
print("BROADCAST PIPELINE AUDIT — LAST 10 SIGNALS (TRACE ONLY)")
print("="*80)
print(f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")

# First, get table columns
cur.execute("PRAGMA table_info(ml_signals)")
columns = {row[1]: row[0] for row in cur.fetchall()}
print(f"DEBUG: ml_signals columns = {list(columns.keys())}\n")

# Get last 10 signals - use only columns we know exist
cur.execute("SELECT id, ticker, interval, signal, timestamp, broadcasted FROM ml_signals ORDER BY id DESC LIMIT 10")
signals = cur.fetchall()

print(f"Found {len(signals)} signals to audit:\n")

for i, sig in enumerate(signals, 1):
    sig_id = sig["id"]
    ticker = sig["ticker"]
    interval = sig["interval"]
    signal_dir = "BUY" if sig["signal"] == 1 else "SELL"
    timestamp = sig["timestamp"]
    broadcasted = sig["broadcasted"]
    
    print(f"{i}. SIGNAL #{sig_id}")
    print(f"   Ticker: {ticker} {interval} {signal_dir}")
    print(f"   Time: {timestamp}")
    print(f"   Broadcasted: {'✅ YES (1)' if broadcasted == 1 else '❌ NO (0)'}")
    print()

db.close()

# Now search logs for DEDUP decisions and broadcast attempts
print("\n" + "="*80)
print("LOG ANALYSIS — DEDUP & BROADCAST DECISIONS")
print("="*80)

# Search for DUPLICATE_PREVENTION in event_debug
print("\n🔍 Searching for DUPLICATE_PREVENTION decisions...")
result = subprocess.run(['tail', '-200', '/home/ubuntu/SilentAnalyst/logs/event_debug.log'], 
                       capture_output=True, text=True, timeout=10)

dedup_lines = [line for line in result.stdout.split('\n') if 'DUPLICATE' in line or 'duplicate' in line]
if dedup_lines:
    print(f"Found {len(dedup_lines)} duplicate prevention events (last 5):")
    for line in dedup_lines[-5:]:
        if 'signal_id' in line.lower() or 'entry' in line.lower():
            print(f"  {line[:140]}")
else:
    print("  No DUPLICATE_PREVENTION events found")

# Search for Telegram send attempts
print("\n🔍 Searching for Telegram broadcast attempts...")
result = subprocess.run(['tail', '-300', '/home/ubuntu/SilentAnalyst/opticore_bot.log'], 
                       capture_output=True, text=True, timeout=10)

bot_log = result.stdout

# Look for success
success_lines = [line for line in bot_log.split('\n') if 'sent successfully' in line.lower()]
if success_lines:
    print(f"✅ Send successes ({len(success_lines)} found):")
    for line in success_lines[-3:]:
        print(f"  {line[:140]}")
else:
    print("✗ No successful sends in recent logs")

# Look for errors
error_lines = [line for line in bot_log.split('\n') if 'error' in line.lower() and 'telegram' in line.lower()]
if error_lines:
    print(f"\n❌ Telegram errors ({len(error_lines)} found):")
    for line in error_lines[-3:]:
        print(f"  {line[:140]}")
else:
    print("\n✗ No Telegram errors in recent logs")

# Look for parse_mode
print("\n🔍 Searching for parse_mode references...")
result = subprocess.run(['grep', '-i', 'parse_mode', '/home/ubuntu/SilentAnalyst/opticore_bot.log'], 
                       capture_output=True, text=True, timeout=10)
if result.stdout:
    lines = result.stdout.strip().split('\n')
    if lines and lines[0]:
        print(f"Found {len(lines)} parse_mode references:")
        for line in lines[-2:]:
            print(f"  {line[:140]}")
else:
    print("✗ No parse_mode found in logs")

print("\n" + "="*80)
print("END OF TRACE")
print("="*80 + "\n")
