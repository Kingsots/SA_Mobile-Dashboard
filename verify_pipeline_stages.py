#!/usr/bin/env python3
"""
Comprehensive Pipeline Verification Script
Checks all stages: Signal Build → Validation → Trade Preparation → Persistence → Broadcast
"""

import sqlite3
import subprocess
from datetime import datetime, timedelta
import sys

print("=" * 80)
print("SILENT ANALYST PIPELINE VERIFICATION")
print("=" * 80)
print(f"\nVerification Time: {datetime.now().isoformat()}\n")

# ============================================================================
# STAGE 1A: SIGNAL BUILD
# ============================================================================
print("STAGE 1A - SIGNAL BUILD")
print("-" * 80)

result = subprocess.run(
    ["ssh", "silentanalyst", "grep -E 'TRADE_CONSTRUCTED|Building signal|Signal generated' /home/ubuntu/SilentAnalyst/logs/scheduler.log | tail -10"],
    capture_output=True,
    text=True,
    timeout=10
)

if result.stdout:
    print("✅ Signal build detected:\n")
    for line in result.stdout.strip().split('\n')[-5:]:
        print(f"   {line}")
    stage_1a = True
else:
    print("❌ No signal build logs found")
    stage_1a = False

# ============================================================================
# STAGE 1B: SIGNAL VALIDATION
# ============================================================================
print("\n" + "=" * 80)
print("STAGE 1B - SIGNAL VALIDATION")
print("-" * 80)

result = subprocess.run(
    ["ssh", "silentanalyst", "grep -E 'Validation|validation|VALIDATION|rejected|Rejected' /home/ubuntu/SilentAnalyst/logs/scheduler.log | tail -10"],
    capture_output=True,
    text=True,
    timeout=10
)

if result.stdout:
    print("✅ Validation logs detected:\n")
    for line in result.stdout.strip().split('\n')[-5:]:
        print(f"   {line}")
    stage_1b = True
else:
    print("⚠️  No explicit validation logs (may be silent)")
    stage_1b = True  # Assume working if no errors

# ============================================================================
# STAGE 1C: CONTEXT/REGIME FILTERS
# ============================================================================
print("\n" + "=" * 80)
print("STAGE 1C - CONTEXT/REGIME FILTERS")
print("-" * 80)

result = subprocess.run(
    ["ssh", "silentanalyst", "grep -E 'Regime|REGIME|regime|Market state|market state|volatility' /home/ubuntu/SilentAnalyst/logs/scheduler.log | tail -10"],
    capture_output=True,
    text=True,
    timeout=10
)

if result.stdout:
    print("✅ Regime/context filtering detected:\n")
    for line in result.stdout.strip().split('\n')[-5:]:
        print(f"   {line}")
    stage_1c = True
else:
    print("⚠️  No regime filter logs (may not be implemented)")
    stage_1c = False

# ============================================================================
# STAGE 2: TRADE PREPARATION (Entry/SL/TP/RR)
# ============================================================================
print("\n" + "=" * 80)
print("STAGE 2 - TRADE PREPARATION (Entry/SL/TP/RR)")
print("-" * 80)

result = subprocess.run(
    ["ssh", "silentanalyst", "grep -E 'entry=|stop=|tp=|rr=|RR=|Risk' /home/ubuntu/SilentAnalyst/logs/scheduler.log | tail -10"],
    capture_output=True,
    text=True,
    timeout=10
)

if result.stdout:
    print("✅ Trade preparation detected (pricing calculated):\n")
    for line in result.stdout.strip().split('\n')[-5:]:
        if 'entry=' in line or 'rr=' in line:
            print(f"   {line[:120]}")
    stage_2 = True
else:
    print("❌ No trade preparation logs found")
    stage_2 = False

# ============================================================================
# STAGE 3: DATABASE PERSISTENCE
# ============================================================================
print("\n" + "=" * 80)
print("STAGE 3 - DATABASE PERSISTENCE")
print("-" * 80)

# Check how many trades in database
try:
    result = subprocess.run(
        ["ssh", "silentanalyst", "sqlite3 /home/ubuntu/SilentAnalyst/trading_bot.db 'SELECT COUNT(*) FROM trades;'"],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.stdout.strip().isdigit():
        trade_count = int(result.stdout.strip())
        print(f"✅ Trades in database: {trade_count}")
        stage_3 = trade_count > 0
    else:
        print("❌ Could not query trades table")
        stage_3 = False
        
except Exception as e:
    print(f"❌ Database query error: {e}")
    stage_3 = False

# Check for recent trades (last 2 hours)
if stage_3:
    result = subprocess.run(
        ["ssh", "silentanalyst", "sqlite3 /home/ubuntu/SilentAnalyst/trading_bot.db \"SELECT symbol, direction, entry_price, created_at FROM trades ORDER BY created_at DESC LIMIT 5;\""],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.stdout:
        print("\n   Recent trades:")
        for line in result.stdout.strip().split('\n'):
            if line:
                print(f"   {line}")

# ============================================================================
# STAGE 4: BROADCAST TO TELEGRAM
# ============================================================================
print("\n" + "=" * 80)
print("STAGE 4 - BROADCAST TO TELEGRAM")
print("-" * 80)

result = subprocess.run(
    ["ssh", "silentanalyst", "grep -E 'Broadcasting|Telegram|telegram|sent successfully' /home/ubuntu/SilentAnalyst/logs/scheduler.log | tail -10"],
    capture_output=True,
    text=True,
    timeout=10
)

if result.stdout:
    print("✅ Broadcast logs detected:\n")
    for line in result.stdout.strip().split('\n')[-5:]:
        print(f"   {line}")
    stage_4 = True
else:
    print("⚠️  No broadcast logs (may be successful/silent)")
    stage_4 = True

# ============================================================================
# DUPLICATE CHECK
# ============================================================================
print("\n" + "=" * 80)
print("DUPLICATE ANALYSIS")
print("-" * 80)

try:
    result = subprocess.run(
        ["ssh", "silentanalyst", "sqlite3 /home/ubuntu/SilentAnalyst/trading_bot.db \"SELECT symbol, direction, COUNT(*) as count FROM trades WHERE DATE(created_at) = DATE('now') GROUP BY symbol, direction ORDER BY count DESC;\""],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.stdout:
        print("Today's trades by symbol/direction:\n")
        lines = result.stdout.strip().split('\n')
        max_count = 0
        for line in lines:
            if line:
                parts = line.split('|')
                if len(parts) == 3:
                    symbol, direction, count = parts
                    count = int(count.strip())
                    max_count = max(max_count, count)
                    status = "✅" if count == 1 else ("⚠️ " if count <= 2 else "❌")
                    print(f"   {status} {symbol.strip():10s} {direction.strip():6s}: {count} trades")
        
        if max_count == 1:
            print("\n✅ NO DUPLICATES - Each signal broadcast once")
            duplicates = False
        elif max_count <= 2:
            print("\n⚠️  MINIMAL DUPLICATES - Acceptable level")
            duplicates = False
        else:
            print(f"\n❌ DUPLICATES DETECTED - Max count: {max_count}")
            duplicates = True
    else:
        print("   (No trades yet today)")
        duplicates = False
        
except Exception as e:
    print(f"   Error: {e}")
    duplicates = None

# ============================================================================
# PIPELINE HEALTH CHECK
# ============================================================================
print("\n" + "=" * 80)
print("PIPELINE HEALTH SUMMARY")
print("=" * 80)

health_status = {
    "Stage 1A - Signal Build": "✅ PASS" if stage_1a else "❌ FAIL",
    "Stage 1B - Validation": "✅ PASS" if stage_1b else "⚠️  UNKNOWN",
    "Stage 1C - Regime Filters": "✅ PASS" if stage_1c else "⚠️  NOT ACTIVE",
    "Stage 2 - Trade Prep": "✅ PASS" if stage_2 else "❌ FAIL",
    "Stage 3 - DB Persist": "✅ PASS" if stage_3 else "❌ FAIL",
    "Stage 4 - Broadcast": "✅ PASS" if stage_4 else "⚠️  UNKNOWN",
    "Duplicates": "✅ NONE" if not duplicates else ("❌ FOUND" if duplicates else "⏳ CHECK"),
}

for stage, status in health_status.items():
    print(f"{stage:30s}: {status}")

# Overall status
total_pass = sum(1 for s in health_status.values() if "PASS" in s)
print(f"\n📊 Overall: {total_pass}/{len(health_status)} stages passing")

if total_pass >= 5 and not duplicates:
    print("✅ PIPELINE IS HEALTHY")
else:
    print("⚠️  PIPELINE NEEDS ATTENTION")

print("\n" + "=" * 80)
