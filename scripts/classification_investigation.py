#!/usr/bin/env python3
"""
CLASSIFICATION INVESTIGATION REPORT
Deep forensic analysis of signal classification layer bias
- NO MODIFICATIONS - INVESTIGATION ONLY
"""
import sqlite3
from datetime import datetime, timedelta, timezone
import argparse
import os
from collections import defaultdict

parser = argparse.ArgumentParser(description='Classification bias investigation')
parser.add_argument('--db', default='trading_bot.db', help='Path to trading_bot.db')
parser.add_argument('--days', type=int, default=20, help='Lookback days')
parser.add_argument('--outdir', default='reports/classification_investigation', help='Output folder')
args = parser.parse_args()

os.makedirs(args.outdir, exist_ok=True)

# Calculate cutoff
base_dt = datetime.now(timezone.utc)
d = base_dt.date()
count = 0
while count < args.days:
    d -= timedelta(days=1)
    if d.weekday() < 5:
        count += 1
cutoff_dt = datetime(d.year, d.month, d.day)
cutoff_iso = cutoff_dt.isoformat()

conn = sqlite3.connect(args.db)
c = conn.cursor()

# ============ LOAD SIGNALS ============
print("=" * 80)
print("CLASSIFICATION INVESTIGATION REPORT")
print("=" * 80)
print(f"Database: {args.db}")
print(f"Period: {cutoff_iso} onwards ({args.days} trading days)\n")

# Query all event-driven signals
c.execute("""
    SELECT id, timestamp, ticker, interval, signal, confidence, model_version, triggered_by 
    FROM ml_signals 
    WHERE triggered_by LIKE 'event:%' AND timestamp >= ?
    ORDER BY timestamp
""", (cutoff_iso,))

all_signals = c.fetchall()
conn.close()

print(f"✅ Loaded {len(all_signals)} event-driven signals\n")

# ============ BASIC DISTRIBUTION ============
signal_map = {1: 'BUY', -1: 'SELL', 0: 'NEUTRAL'}
signal_counts = defaultdict(int)
confidence_by_signal = defaultdict(list)

for row in all_signals:
    signal_label = signal_map.get(row[4], 'UNKNOWN')
    signal_counts[signal_label] += 1
    confidence_by_signal[signal_label].append(row[5])

total = len(all_signals)
print("1. FINAL SIGNAL DISTRIBUTION")
print("-" * 80)
for direction in ['BUY', 'SELL', 'NEUTRAL']:
    count = signal_counts[direction]
    pct = (count / total * 100) if total > 0 else 0
    print(f"  {direction:8} : {count:6} ({pct:6.1f}%)")
print(f"  TOTAL    : {total:6}\n")

# ============ EVENT TYPE BREAKDOWN ============
print("2. EVENT TYPE → DIRECTION MAPPING")
print("-" * 80)

event_direction_stats = defaultdict(lambda: {'BUY': 0, 'SELL': 0, 'NEUTRAL': 0})

for row in all_signals:
    event_type = row[7]
    signal_label = signal_map.get(row[4], 'UNKNOWN')
    event_direction_stats[event_type][signal_label] += 1

print(f"{'Event Type':<45} {'BUY':>6} {'SELL':>6} {'NEUTRAL':>8} {'%BUY':>6}")
print("-" * 80)

for event_type in sorted(event_direction_stats.keys(), key=lambda x: sum(event_direction_stats[x].values()), reverse=True):
    stats = event_direction_stats[event_type]
    total_evt = stats['BUY'] + stats['SELL'] + stats['NEUTRAL']
    pct_buy = (stats['BUY'] / total_evt * 100) if total_evt > 0 else 0
    
    print(f"{event_type:<45} {stats['BUY']:>6} {stats['SELL']:>6} {stats['NEUTRAL']:>8} {pct_buy:>6.1f}%")

print()

# ============ CRITICAL FLAGS ============
print("3. CRITICAL FINDINGS")
print("-" * 80)

critical_flags = []

if signal_counts['SELL'] == 0:
    print("🚨 CRITICAL: ZERO SELL SIGNALS in entire dataset!")
    critical_flags.append("ZERO_SELL_SIGNALS")

if signal_counts['SELL'] < total * 0.05:
    print(f"🚨 CRITICAL: SELL signals < 5% (actual: {signal_counts['SELL']/total*100:.1f}%)")
    critical_flags.append("SELL_LESS_THAN_5_PERCENT")

# Check bearish events
bearish_events = [
    'event:rsi_rejection_bearish',
    'event:trendline_break_support',
    'event:engulfed_structure_bearish'
]

for event in bearish_events:
    if event in event_direction_stats:
        stats = event_direction_stats[event]
        total_evt = stats['BUY'] + stats['SELL'] + stats['NEUTRAL']
        if stats['SELL'] == 0 and total_evt > 0:
            print(f"🚨 FLAG: {event} produces ZERO SELL ({total_evt} total signals)")
            critical_flags.append(f"ZERO_SELL_{event}")

if not critical_flags:
    print("✅ No critical flags detected (SELL signals present)")

print()

# ============ CONFIDENCE ANALYSIS ============
print("4. CONFIDENCE DISTRIBUTION BY DIRECTION")
print("-" * 80)
print(f"{'Direction':<10} {'Count':>6} {'Mean':>10} {'Median':>10} {'Min':>10} {'Max':>10}")
print("-" * 80)

for direction in ['BUY', 'SELL', 'NEUTRAL']:
    conf_list = sorted(confidence_by_signal[direction])
    if len(conf_list) > 0:
        mean_conf = sum(conf_list) / len(conf_list)
        median_conf = conf_list[len(conf_list) // 2]
        min_conf = min(conf_list)
        max_conf = max(conf_list)
        
        print(f"{direction:<10} {len(conf_list):>6} {mean_conf:>10.4f} {median_conf:>10.4f} {min_conf:>10.4f} {max_conf:>10.4f}")

print()

# ============ TICKER BIAS ============
print("5. PER-TICKER DIRECTIONAL BIAS")
print("-" * 80)
print(f"{'Ticker':<10} {'BUY':>6} {'SELL':>6} {'NEUTRAL':>8} {'Total':>6} {'%BUY':>6} {'%SELL':>6}")
print("-" * 80)

ticker_stats = defaultdict(lambda: {'BUY': 0, 'SELL': 0, 'NEUTRAL': 0})
for row in all_signals:
    ticker = row[2]
    signal_label = signal_map.get(row[4], 'UNKNOWN')
    ticker_stats[ticker][signal_label] += 1

extreme_bias = []
for ticker in sorted(ticker_stats.keys()):
    stats = ticker_stats[ticker]
    total_t = stats['BUY'] + stats['SELL'] + stats['NEUTRAL']
    pct_buy = (stats['BUY'] / total_t * 100) if total_t > 0 else 0
    pct_sell = (stats['SELL'] / total_t * 100) if total_t > 0 else 0
    
    print(f"{ticker:<10} {stats['BUY']:>6} {stats['SELL']:>6} {stats['NEUTRAL']:>8} {total_t:>6} {pct_buy:>6.1f}% {pct_sell:>6.1f}%")
    
    if pct_buy > 90 or pct_sell > 90:
        extreme_bias.append((ticker, pct_buy, pct_sell))

if extreme_bias:
    print()
    print("⚠️  EXTREME BIAS DETECTED:")
    for ticker, pct_buy, pct_sell in extreme_bias:
        print(f"   {ticker}: {pct_buy:.1f}% BUY / {pct_sell:.1f}% SELL")

print()

# ============ ROOT CAUSE ANALYSIS ============
print("6. ROOT CAUSE HYPOTHESIS")
print("-" * 80)

if signal_counts['SELL'] == 0:
    print("SELL signals are NEVER generated. Possible causes:\n")
    print("  A) Hard-coded fallback: if not BUY_condition: return BUY (not SELL)")
    print("  B) Asymmetric threshold: SELL requires extremely negative score (unreachable)")
    print("  C) Logic gate: Fallback prevents any SELL output")
    print("  D) Direction inversion: Bearish events scored as bullish")
    print("  E) Broken bearish event detection")
    print("\nTO DEBUG:")
    print("  1. Search codebase for: 'default.*BUY' or 'fallback.*BUY'")
    print("  2. Verify: threshold_sell < threshold_buy in decision function")
    print("  3. Check: Model outputs raw scores (not just BUY/NEUTRAL)")
    print("  4. Trace: How bearish events map to negative scores")

elif signal_counts['SELL'] < total * 0.05:
    print("SELL signals are EXTREMELY RARE (<5%). Possible causes:\n")
    print("  A) SELL threshold is too strict (high bar)")
    print("  B) Bearish event confidence too low to trigger SELL")
    print("  C) Trend filter blocking SELL signals")
    print("  D) Regime detection preferring BUY")

else:
    print("✅ Balanced signal distribution detected (further analysis needed)")

print()

# ============ WRITE REPORT FILE ============
report_path = os.path.join(args.outdir, 'INVESTIGATION_REPORT.txt')

with open(report_path, 'w') as f:
    f.write("=" * 80 + "\n")
    f.write("CLASSIFICATION BIAS INVESTIGATION REPORT\n")
    f.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n")
    f.write(f"Database: {args.db}\n")
    f.write(f"Period: {cutoff_iso} onwards ({args.days} trading days)\n")
    f.write("=" * 80 + "\n\n")
    
    f.write("1. FINAL SIGNAL DISTRIBUTION\n")
    f.write("-" * 80 + "\n")
    for direction in ['BUY', 'SELL', 'NEUTRAL']:
        count = signal_counts[direction]
        pct = (count / total * 100) if total > 0 else 0
        f.write(f"  {direction:8} : {count:6} ({pct:6.1f}%)\n")
    f.write(f"  TOTAL    : {total:6}\n\n")
    
    f.write("2. EVENT TYPE BREAKDOWN\n")
    f.write("-" * 80 + "\n")
    f.write(f"{'Event Type':<45} {'BUY':>6} {'SELL':>6} {'NEUTRAL':>8}\n")
    f.write("-" * 80 + "\n")
    for event_type in sorted(event_direction_stats.keys(), key=lambda x: sum(event_direction_stats[x].values()), reverse=True):
        stats = event_direction_stats[event_type]
        f.write(f"{event_type:<45} {stats['BUY']:>6} {stats['SELL']:>6} {stats['NEUTRAL']:>8}\n")
    
    f.write("\n3. CRITICAL FLAGS\n")
    f.write("-" * 80 + "\n")
    if critical_flags:
        for flag in critical_flags:
            f.write(f"  🚨 {flag}\n")
    else:
        f.write("  ✅ No critical flags detected\n")
    
    f.write("\n4. CONFIDENCE STATISTICS\n")
    f.write("-" * 80 + "\n")
    for direction in ['BUY', 'SELL', 'NEUTRAL']:
        conf_list = sorted(confidence_by_signal[direction])
        if len(conf_list) > 0:
            mean_conf = sum(conf_list) / len(conf_list)
            f.write(f"  {direction}: mean={mean_conf:.4f}, n={len(conf_list)}\n")

print(f"✅ Report saved: {report_path}")
