#!/usr/bin/env python3
"""
Pipeline Verification - Version 2 (Simpler subprocess handling)
"""

import subprocess
from datetime import datetime

def run_ssh_cmd(cmd):
    """Run command via SSH and return output"""
    try:
        result = subprocess.run(
            ["ssh", "silentanalyst", cmd],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception as e:
        print(f"   Error: {e}")
        return None

print("=" * 80)
print("SILENT ANALYST - PIPELINE VERIFICATION (V2)")
print("=" * 80)
print(f"Time: {datetime.now().isoformat()}\n")

# Stage 1A
print("STAGE 1A - SIGNAL BUILD")
print("-" * 80)
logs = run_ssh_cmd("tail -20 /home/ubuntu/SilentAnalyst/logs/scheduler.log | grep TRADE_CONSTRUCTED")
if logs:
    print(f"✅ Signals built:\n{logs}")
    stage_1a = True
else:
    print("❌ No TRADE_CONSTRUCTED logs")
    stage_1a = False

# Stage 2
print("\nSTAGE 2 - TRADE PREPARATION")
print("-" * 80)
logs = run_ssh_cmd("tail -20 /home/ubuntu/SilentAnalyst/logs/scheduler.log | grep 'entry='")
if logs:
    print(f"✅ Trade pricing calculated:\n{logs}")
    stage_2 = True
else:
    print("❌ No entry/SL/TP logs")
    stage_2 = False

# Stage 3
print("\nSTAGE 3 - DATABASE PERSISTENCE")
print("-" * 80)
count = run_ssh_cmd("sqlite3 /home/ubuntu/SilentAnalyst/trading_bot.db 'SELECT COUNT(*) FROM trades;'")
if count and count.isdigit():
    trade_count = int(count)
    print(f"✅ Trades in database: {trade_count}")
    stage_3 = trade_count > 0
    
    # Show recent trades
    if trade_count > 0:
        recent = run_ssh_cmd("sqlite3 /home/ubuntu/SilentAnalyst/trading_bot.db 'SELECT symbol, direction, entry_price, created_at FROM trades ORDER BY created_at DESC LIMIT 3;'")
        if recent:
            print("   Recent trades:")
            for line in recent.split('\n'):
                if line:
                    print(f"   {line}")
else:
    print("❌ Could not query trades table")
    stage_3 = False

# Stage 4
print("\nSTAGE 4 - BROADCAST TO TELEGRAM")
print("-" * 80)
logs = run_ssh_cmd("tail -20 /home/ubuntu/SilentAnalyst/logs/scheduler.log | grep -i 'telegram\\|broadcast'")
if logs:
    print(f"✅ Broadcasts detected:\n{logs}")
    stage_4 = True
else:
    print("⚠️  No broadcast logs")
    stage_4 = False

# Duplicates
print("\nDUPLICATE CHECK")
print("-" * 80)
dups = run_ssh_cmd("sqlite3 /home/ubuntu/SilentAnalyst/trading_bot.db \"SELECT symbol, direction, COUNT(*) as cnt FROM trades WHERE DATE(created_at) = DATE('now') GROUP BY symbol, direction ORDER BY cnt DESC;\"")
if dups:
    print("Today's trades:")
    max_count = 0
    for line in dups.split('\n'):
        if line:
            print(f"   {line}")
            parts = line.split('|')
            if len(parts) == 3:
                try:
                    cnt = int(parts[2].strip())
                    max_count = max(max_count, cnt)
                except:
                    pass
    
    if max_count <= 1:
        print("\n✅ NO DUPLICATES")
        stage_dup = True
    else:
        print(f"\n❌ DUPLICATES: Max count {max_count}")
        stage_dup = False
else:
    print("(No trades today yet)")
    stage_dup = True

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Stage 1A (Build):     {'✅ PASS' if stage_1a else '❌ FAIL'}")
print(f"Stage 2 (Prep):       {'✅ PASS' if stage_2 else '❌ FAIL'}")
print(f"Stage 3 (Persist):    {'✅ PASS' if stage_3 else '❌ FAIL'}")
print(f"Stage 4 (Broadcast):  {'✅ PASS' if stage_4 else '⚠️  UNKNOWN'}")
print(f"Duplicates:           {'✅ NONE' if stage_dup else '❌ FOUND'}")

if stage_1a and stage_2 and stage_3 and stage_dup:
    print("\n✅ PIPELINE IS HEALTHY")
else:
    print("\n⚠️  WAITING FOR NEXT SIGNAL (next sweep ~20:35 UTC)")
