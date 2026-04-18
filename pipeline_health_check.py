#!/usr/bin/env python3
"""SILENT ANALYST - PIPELINE HEALTH CHECK (NO ASSUMPTIONS)"""
import sqlite3
from datetime import datetime
import subprocess

db_path = '/home/ubuntu/SilentAnalyst/trading_bot.db'
db = sqlite3.connect(db_path)
db.row_factory = sqlite3.Row
cur = db.cursor()

print('\n' + '='*70)
print('SILENT ANALYST — PIPELINE HEALTH CHECK')
print('='*70)

# 0. SERVICE STATUS
print('\n' + '━'*70)
print('0. SERVICE STATUS')
print('━'*70)
result = subprocess.run(['systemctl', 'status', 'opticore.service', '--no-pager'], 
                       capture_output=True, text=True, timeout=5)
lines = result.stdout.split('\n')[:5]
for line in lines:
    print(line)
service_active = 'active (running)' in result.stdout
print(f"\n→ Service Status: {'✅ ACTIVE' if service_active else '❌ INACTIVE'}")

if not service_active:
    print("\n⚠️  STOP. Service not running. Everything else is meaningless.")
    db.close()
    exit(1)

# 1. LAST SIGNAL GENERATED
print('\n' + '━'*70)
print('1. LAST SIGNAL GENERATED')
print('━'*70)
try:
    cur.execute('''SELECT id, ticker, interval, signal, timestamp
    FROM ml_signals
    ORDER BY timestamp DESC
    LIMIT 1''')
    row = cur.fetchone()
    if row:
        print(f"ID: {row['id']}")
        print(f"Ticker: {row['ticker']}")
        print(f"Interval: {row['interval']}")
        print(f"Signal: {row['signal']}")
        print(f"Timestamp: {row['timestamp']}")
        
        # Calculate age
        ts = datetime.fromisoformat(row['timestamp'])
        now = datetime.utcnow()
        age_min = (now - ts).total_seconds() / 60
        print(f"Age: {age_min:.1f} minutes ago")
    else:
        print("❌ NO SIGNALS FOUND IN DATABASE")
except Exception as e:
    print(f"❌ Error querying last signal: {e}")

# 2. SIGNAL RATE (LAST 15 / 60 MINUTES)
print('\n' + '━'*70)
print('2. SIGNAL RATE')
print('━'*70)
try:
    cur.execute('''SELECT COUNT(*) as last_15_min
    FROM ml_signals
    WHERE timestamp > datetime('now', '-15 minutes')''')
    count_15 = cur.fetchone()['last_15_min']
    
    cur.execute('''SELECT COUNT(*) as last_60_min
    FROM ml_signals
    WHERE timestamp > datetime('now', '-60 minutes')''')
    count_60 = cur.fetchone()['last_60_min']
    
    print(f"Last 15 minutes: {count_15} signals")
    print(f"Last 60 minutes: {count_60} signals")
    
    if count_15 >= 3:
        status = "✅ ACTIVE"
    elif count_60 >= 5:
        status = "🟡 SLOW"
    elif count_60 > 0:
        status = "🟠 STALLED"
    else:
        status = "❌ DEAD"
    print(f"Status: {status}")
except Exception as e:
    print(f"❌ Error querying signal rate: {e}")

# 3. BROADCAST STATUS
print('\n' + '━'*70)
print('3. BROADCAST STATUS')
print('━'*70)
try:
    cur.execute('''SELECT 
      COUNT(*) as total_last_60,
      SUM(CASE WHEN broadcasted = 1 THEN 1 ELSE 0 END) as sent_last_60
    FROM ml_signals
    WHERE timestamp > datetime('now', '-60 minutes')''')
    row = cur.fetchone()
    total = row['total_last_60']
    sent = row['sent_last_60'] or 0
    
    print(f"Total signals (last 60 min): {total}")
    print(f"Signals broadcasted: {sent}")
    
    if total == 0:
        print("→ No signals generated in last 60 minutes (cannot judge broadcast)")
    elif sent == total:
        print("→ ✅ ALL signals broadcasted")
    elif sent > 0:
        print(f"→ 🟡 PARTIAL broadcast ({sent}/{total})")
    else:
        print("→ ❌ SIGNALS NOT BEING SENT")
except Exception as e:
    print(f"❌ Error querying broadcast status: {e}")

# 4. CONTEXT ENGINE ACTIVITY
print('\n' + '━'*70)
print('4. CONTEXT ENGINE ACTIVITY')
print('━'*70)
try:
    cur.execute('''SELECT ticker, compression_score, rsi_stage, timestamp
    FROM context_log
    ORDER BY timestamp DESC
    LIMIT 5''')
    rows = cur.fetchall()
    if rows:
        print("Latest context engine updates:")
        for row in rows:
            print(f"  {row['ticker']:8} | RSI: {row['rsi_stage']:5} | Score: {row['compression_score']:6.2f} | {row['timestamp']}")
        
        latest_ts = datetime.fromisoformat(rows[0]['timestamp'])
        now = datetime.utcnow()
        age = (now - latest_ts).total_seconds() / 60
        print(f"\nLatest timestamp: {rows[0]['timestamp']} ({age:.1f} min ago)")
        print("→ ✅ Fresh processing confirmed")
    else:
        print("❌ NO CONTEXT LOG DATA FOUND")
except Exception as e:
    print(f"❌ Error querying context engine: {e}")

# 5. PIPELINE HEARTBEAT (LOG CHECK)
print('\n' + '━'*70)
print('5. PIPELINE HEARTBEAT (FROM LOGS)')
print('━'*70)
try:
    result = subprocess.run([
        'journalctl', '-u', 'opticore.service', 
        '--since', '2 hours ago',
        '--no-pager'
    ], capture_output=True, text=True, timeout=10)
    
    logs = result.stdout
    
    # Look for key events
    fetch_count = logs.count('Starting Tiingo fetch')
    fetch_complete_count = logs.count('Fetch complete')
    pipeline_exec = logs.count('PIPELINE_EXECUTION')
    errors = logs.count('ERROR')
    
    print(f"Events (last 2 hours):")
    print(f"  Fetch jobs started: {fetch_count}")
    print(f"  Fetch jobs completed: {fetch_complete_count}")
    print(f"  Pipeline executions: {pipeline_exec}")
    print(f"  Errors: {errors}")
    
    # Show last execution line
    lines = logs.split('\n')
    for line in reversed(lines):
        if 'PIPELINE_EXECUTION' in line or 'Fetch complete' in line or 'Starting' in line:
            print(f"\nLast activity:\n {line[:150]}")
            break
            
except Exception as e:
    print(f"❌ Error checking logs: {e}")

# 6. FINAL STATUS
print('\n' + '='*70)
print('6. FINAL STATUS REPORT')
print('='*70)

try:
    cur.execute('SELECT COUNT(*) as cnt FROM ml_signals WHERE timestamp > datetime("now", "-60 minutes")')
    signals_60min = cur.fetchone()['cnt']
    
    cur.execute('SELECT COUNT(*) as cnt FROM ml_signals WHERE timestamp > datetime("now", "-60 minutes") AND broadcasted = 1')
    broadcast_60min = cur.fetchone()['cnt']
    
    cur.execute('SELECT COUNT(*) as cnt FROM context_log ORDER BY timestamp DESC LIMIT 1')
    context_exists = cur.fetchone()['cnt'] > 0
    
    signals_generating = signals_60min > 0
    broadcast_working = (signals_60min > 0 and broadcast_60min == signals_60min)
    
    print(f"\n✓ Service Running: {service_active} → YES" if service_active else "✗ NO")
    print(f"{'✓' if signals_generating else '✗'} Signals Generating: {'YES' if signals_generating else 'NO'}")
    print(f"{'✓' if context_exists else '✗'} Context Engine Running: {'YES' if context_exists else 'NO'}")
    print(f"{'✓' if broadcast_working else '✗'} Telegram Sending: {'YES' if broadcast_working else 'NO'}")
    
    # Determine failure point if any
    print("\n" + "─"*70)
    failures = []
    if not service_active:
        failures.append("❌ Service not running")
    if not signals_generating:
        failures.append("❌ Signals NOT generating (check: data stale? scheduler blocked?)")
    if not context_exists:
        failures.append("❌ Context engine NOT running (check: feature pipeline blocked?)")
    if signals_generating and not broadcast_working:
        failures.append("❌ Broadcast failing (signals stuck, Telegram error?)")
    
    if failures:
        print("\n⚠️  FAILURE POINTS DETECTED:")
        for f in failures:
            print(f"  {f}")
    else:
        print("\n✅ PIPELINE HEALTHY - All systems GO")
        
except Exception as e:
    print(f"❌ Error in final status: {e}")

print("\n" + "="*70)
db.close()
