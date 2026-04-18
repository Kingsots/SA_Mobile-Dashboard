#!/usr/bin/env python3
"""SILENT ANALYST - COMPREHENSIVE PIPELINE HEALTH REPORT (UNIFIED)"""
import sqlite3
from datetime import datetime, timezone
import subprocess

db_path = '/home/ubuntu/SilentAnalyst/trading_bot.db'
db = sqlite3.connect(db_path)
db.row_factory = sqlite3.Row
cur = db.cursor()

print('\n' + '='*70)
print('SILENT ANALYST — COMPREHENSIVE PIPELINE HEALTH REPORT')
print('='*70)
print(f'\n📊 REPORT TIMESTAMP: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}')

# 0. SERVICE STATUS
print('\n' + '━'*70)
print('0. SERVICE STATUS')
print('━'*70)
result = subprocess.run(['systemctl', 'status', 'opticore.service', '--no-pager'], 
                       capture_output=True, text=True, timeout=5)
service_active = 'active (running)' in result.stdout
status_line = [line for line in result.stdout.split('\n') if 'Active:' in line]
if status_line:
    print(f"  {status_line[0].strip()}")
print(f"\n  Status: {'✅ ACTIVE' if service_active else '❌ INACTIVE'}")

if not service_active:
    print("\n  ⚠️  CRITICAL: Service not running. Cannot proceed.")
    db.close()
    exit(1)

# 1. SIGNAL GENERATION
print('\n' + '━'*70)
print('1. SIGNAL GENERATION')
print('━'*70)

cur.execute('SELECT id, ticker, signal, timestamp FROM ml_signals ORDER BY timestamp DESC LIMIT 1')
last_signal = cur.fetchone()

if last_signal:
    print(f"\n  Last Signal Generated:")
    print(f"    ID:        {last_signal['id']}")
    print(f"    Ticker:    {last_signal['ticker']}")
    print(f"    Direction: {'BUY' if last_signal['signal'] == 1 else 'SELL'}")
    print(f"    Timestamp: {last_signal['timestamp']}")
else:
    print("  ❌ No signals found in database")

cur.execute('SELECT COUNT(*) as cnt FROM ml_signals WHERE timestamp > datetime("now", "-15 minutes")')
count_15 = cur.fetchone()['cnt']

cur.execute('SELECT COUNT(*) as cnt FROM ml_signals WHERE timestamp > datetime("now", "-60 minutes")')
count_60 = cur.fetchone()['cnt']

print(f"\n  Signal Rate:")
print(f"    Last 15 min: {count_15} signals")
print(f"    Last 60 min: {count_60} signals")

if count_15 >= 3:
    rate_status = "✅ ACTIVE"
elif count_60 >= 5:
    rate_status = "🟡 SLOW"
elif count_60 > 0:
    rate_status = "🟠 STALLED"
else:
    rate_status = "❌ DEAD (No signals)"
print(f"    Status: {rate_status}")

# 2. BROADCAST STATUS
print('\n' + '━'*70)
print('2. BROADCAST STATUS')
print('━'*70)

cur.execute('SELECT COUNT(*) as total, SUM(broadcasted) as sent FROM ml_signals WHERE timestamp > datetime("now", "-60 minutes")')
broadcast_row = cur.fetchone()
total_60 = broadcast_row['total']
sent_60 = broadcast_row['sent'] or 0

print(f"\n  Signals Last 60 Min:")
print(f"    Total Generated: {total_60}")
print(f"    Sent to Telegram: {sent_60}")

if total_60 == 0:
    bcast_status = "⚠️  Cannot assess (no signals)"
elif sent_60 == total_60:
    bcast_status = "✅ ALL signals sent"
elif sent_60 > 0:
    bcast_status = f"🟡 PARTIAL ({sent_60}/{total_60} sent)"
else:
    bcast_status = "❌ NO signals sent"

print(f"    Status: {bcast_status}")

# Check for duplicate prevention
if sent_60 == 0 and total_60 > 0:
    result = subprocess.run(['journalctl', '-u', 'opticore.service', '-n', '100', '--no-pager'], 
                           capture_output=True, text=True, timeout=10)
    if 'DUPLICATE_PREVENTION' in result.stdout:
        print(f"\n  ⚠️  NOTE: Duplicate prevention active (blocking recent re-sends)")

# 3. CONTEXT ENGINE  
print('\n' + '━'*70)
print('3. CONTEXT ENGINE ACTIVITY')
print('━'*70)

cur.execute('SELECT ticker, compression_score, rsi_stage, timestamp FROM context_log ORDER BY timestamp DESC LIMIT 5')
context_rows = cur.fetchall()

if context_rows:
    print(f"\n  Latest Context Updates:")
    for i, row in enumerate(context_rows[:3], 1):
        print(f"    {i}. {row['ticker']:8} | RSI: {row['rsi_stage']:5} | Score: {row['compression_score']:.2f} | {row['timestamp']}")
    
    latest_ts = datetime.fromisoformat(context_rows[0]['timestamp'])
    now = datetime.now(timezone.utc)
    age_min = (now - latest_ts).total_seconds() / 60
    
    print(f"\n  Freshness: {age_min:.0f} minutes old")
    if age_min < 10:
        context_status = "✅ Fresh (ACTIVE)"
    elif age_min < 120:
        context_status = "🟡 Recent"
    else:
        context_status = "❌ Stale"
    print(f"  Status: {context_status}")
else:
    print("  ❌ No context engine data found")

# 4. PIPELINE HEARTBEAT
print('\n' + '━'*70)
print('4. PIPELINE HEARTBEAT (LAST 2 HOURS)')
print('━'*70)

result = subprocess.run(['journalctl', '-u', 'opticore.service', '--since', '2 hours ago', '--no-pager'], 
                       capture_output=True, text=True, timeout=10)
logs = result.stdout

fetch_count = logs.count('Starting Tiingo fetch')
fetch_complete = logs.count('Fetch complete')
pipeline_exec = logs.count('PIPELINE_EXECUTION')
errors = logs.count('ERROR')

print(f"\n  Event Counts:")
print(f"    Fetch jobs started: {fetch_count}")
print(f"    Fetch jobs completed: {fetch_complete}")
print(f"    Pipeline executions: {pipeline_exec}")
print(f"    Errors logged: {errors}")

# 5. FINAL DIAGNOSIS
print('\n' + '='*70)
print('5. FINAL DIAGNOSIS')
print('='*70)

print(f"\n  Component Status:")
print(f"    Service Running:      {'✅ YES' if service_active else '❌ NO'}")
print(f"    Signals Generating:   {'✅ YES' if count_60 > 0 else '❌ NO'}")
print(f"    Context Engine:       {'✅ YES' if context_rows else '❌ NO'}")
print(f"    Telegram Broadcast:   {'✅ YES' if sent_60 > 0 else '❌ NO / ⚠️ BLOCKED'}")

print(f"\n  Overall Health: ", end='')

if service_active and count_60 > 0 and context_rows and sent_60 > 0:
    print("✅ HEALTHY - All systems operational")
elif service_active and count_60 > 0 and context_rows:
    print("🟡 OPERATIONAL - Signals blocked by deduplication or other filter")
elif service_active and context_rows:
    print("⚠️  PARTIALLY OPERATIONAL - No new signals but infrastructure active")
elif service_active:
    print("❌ DEGRADED - Service running but pipeline inactive")
else:
    print("❌ CRITICAL - Service not running")

print('\n' + '='*70)
db.close()
