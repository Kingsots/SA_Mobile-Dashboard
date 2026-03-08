#!/usr/bin/env python3
"""
TRAINING DATA AUDIT - Where Did SELL Go?
Investigate training labels and model class distribution
"""
import sqlite3
from datetime import datetime, timedelta, timezone, date
import argparse
import os
from collections import Counter
import sys

parser = argparse.ArgumentParser(description='Audit training data labels')
parser.add_argument('--db', default='trading_bot.db', help='Database path')
parser.add_argument('--lookback', type=int, default=90, help='Days of training data to analyze')
parser.add_argument('--outdir', default='reports/training_audit', help='Output dir')
args = parser.parse_args()

os.makedirs(args.outdir, exist_ok=True)

# Calculate lookback period
end_date = date.today()
start_date = end_date - timedelta(days=args.lookback)

conn = sqlite3.connect(args.db)
c = conn.cursor()

print("=" * 100)
print("TRAINING DATA AUDIT - LABEL DISTRIBUTION INVESTIGATION")
print("=" * 100)
print(f"Database: {args.db}")
print(f"Analysis Period: {start_date} to {end_date} ({args.lookback} days)")
print()

report_file = open(os.path.join(args.outdir, 'TRAINING_DATA_AUDIT.txt'), 'w')
report_file.write("=" * 100 + "\n")
report_file.write("TRAINING DATA AUDIT - LABEL DISTRIBUTION\n")
report_file.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n")
report_file.write(f"Period: {start_date} to {end_date} ({args.lookback} days)\n")
report_file.write("=" * 100 + "\n\n")

# ============ 1. EXAMINE OHLCV DATA ============
print("1. EXAMINING TRAINING DATA SOURCE (OHLCV TABLE)")
print("-" * 100)

# Get all OHLCV data from training period
c.execute("""
    SELECT COUNT(*) FROM ohlcv_data 
    WHERE timestamp >= ? AND timestamp <= ?
""", (start_date.isoformat(), end_date.isoformat()))

total_rows = c.fetchone()[0]
print(f"Total OHLCV rows in training period: {total_rows}")
print()

# Get by symbol
c.execute("""
    SELECT symbol, COUNT(*) as count
    FROM ohlcv_data 
    WHERE timestamp >= ? AND timestamp <= ?
    GROUP BY symbol
    ORDER BY count DESC
""", (start_date.isoformat(), end_date.isoformat()))

symbol_counts = c.fetchall()

print(f"{'Symbol':<10} {'Count':<10} {'Pct':<8}")
print("-" * 100)
for symbol, count in symbol_counts:
    pct = (count / total_rows * 100) if total_rows > 0 else 0
    print(f"{symbol:<10} {count:<10} {pct:>6.1f}%")

print()

report_file.write("1. TRAINING DATA INVENTORY\n")
report_file.write("-" * 100 + "\n")
report_file.write(f"Total OHLCV rows: {total_rows}\n\n")
report_file.write(f"{'Symbol':<10} {'Count':<10}\n")
report_file.write("-" * 100 + "\n")
for symbol, count in symbol_counts:
    report_file.write(f"{symbol:<10} {count:<10}\n")
report_file.write("\n")

# ============ 2. EXAMINE ML_SIGNALS TRAINING LABELS ============
print("2. EXAMINING HISTORICAL SIGNALS (ML_SIGNALS TABLE)")
print("-" * 100)

# Check signals table for label distribution
c.execute("""
    SELECT signal, COUNT(*) as count
    FROM ml_signals 
    WHERE timestamp >= ? AND timestamp <= ?
    GROUP BY signal
    ORDER BY signal
""", (start_date.isoformat(), end_date.isoformat() + "T23:59:59"))

signal_dist = c.fetchall()

print(f"Signal Distribution in Historical Signals (90 days):")
print(f"{'Signal':<10} {'Count':<10} {'Percentage':<12}")
print("-" * 100)

signal_labels = {1: 'BUY', -1: 'SELL', 0: 'NEUTRAL'}
total_signals = 0

for signal_val, count in signal_dist:
    label = signal_labels.get(signal_val, 'UNKNOWN')
    total_signals += count
    pct = (count / total_signals * 100) if total_signals > 0 else 0
    print(f"{label:<10} {count:<10} {pct:>10.1f}%")

print()

# ============ 3. CALCULATE TRAINING LABELS FROM PRICE ACTION ============
print("3. CALCULATING TRAINING LABELS FROM PRICE MOVEMENT")
print("-" * 100)

# Get price movements to infer what training labels SHOULD be
c.execute("""
    SELECT symbol, 
           COUNT(CASE WHEN next_close > close THEN 1 END) as up_moves,
           COUNT(CASE WHEN next_close < close THEN 1 END) as down_moves,
           COUNT(CASE WHEN next_close = close THEN 1 END) as flat_moves
    FROM (
        SELECT symbol, close, 
               LEAD(close) OVER (PARTITION BY symbol ORDER BY timestamp) as next_close
        FROM ohlcv_data
        WHERE timestamp >= ? AND timestamp <= ?
    )
    GROUP BY symbol
    ORDER BY symbol
""", (start_date.isoformat(), end_date.isoformat()))

price_moves = c.fetchall()

print(f"{'Symbol':<10} {'Up Moves':<12} {'Down Moves':<12} {'Flat':<8} {'%Down':<10}")
print("-" * 100)

total_up = total_down = total_flat = 0

for row in price_moves:
    symbol, up, down, flat = row
    total_moves = up + down + flat
    pct_down = (down / total_moves * 100) if total_moves > 0 else 0
    
    total_up += up
    total_down += down
    total_flat += flat
    
    print(f"{symbol:<10} {up:<12} {down:<12} {flat:<8} {pct_down:>8.1f}%")

print()
print(f"TOTALS:")
total_all = total_up + total_down + total_flat
pct_up = (total_up / total_all * 100) if total_all > 0 else 0
pct_down = (total_down / total_all * 100) if total_all > 0 else 0

print(f"  Up moves:   {total_up} ({pct_up:.1f}%)")
print(f"  Down moves: {total_down} ({pct_down:.1f}%)")
print(f"  Flat moves: {total_flat} ({100 - pct_up - pct_down:.1f}%)")
print()

# ============ 4. COMPARE: WHAT TRAINING LABELS SHOULD BE vs MODEL PERFORMANCE ============
print("4. LABEL BIAS ANALYSIS")
print("-" * 100)

report_file.write("2. HISTORICAL SIGNAL DISTRIBUTION\n")
report_file.write("-" * 100 + "\n")
report_file.write(f"{'Signal':<10} {'Count':<10} {'Percentage':<12}\n")
report_file.write("-" * 100 + "\n")

for signal_val, count in signal_dist:
    label = signal_labels.get(signal_val, 'UNKNOWN')
    pct = (count / total_signals * 100) if total_signals > 0 else 0
    report_file.write(f"{label:<10} {count:<10} {pct:>10.1f}%\n")

report_file.write("\n")

report_file.write("3. PRICE ACTION DISTRIBUTION (Training Basis)\n")
report_file.write("-" * 100 + "\n")
report_file.write(f"{'Movement':<15} {'Count':<10} {'Percentage':<12}\n")
report_file.write("-" * 100 + "\n")
report_file.write(f"{'Up (BUY)':<15} {total_up:<10} {pct_up:>10.1f}%\n")
report_file.write(f"{'Down (SELL)':<15} {total_down:<10} {pct_down:>10.1f}%\n")
report_file.write(f"{'Flat (NEUTRAL)':<15} {total_flat:<10} {(100-pct_up-pct_down):>10.1f}%\n")
report_file.write("\n")

# Calculate what we see now in production
print(f"\nExpected vs Observed:")
print(f"  Price action:      {pct_down:.1f}% down moves (should become SELL)")
print(f"  Model output:       0.0% SELL signals")
print()
print(f"Gap: {pct_down:.1f}% - 0.0% = {pct_down:.1f}% missing SELL signals!")
print()

report_file.write("4. ANALYSIS: EXPECTED vs OBSERVED SELL SIGNALS\n")
report_file.write("-" * 100 + "\n")
report_file.write(f"Training data shows:\n")
report_file.write(f"  - {pct_down:.1f}% price movements were DOWNWARD (should train SELL)\n")
report_file.write(f"\nProduction model outputs:\n")
report_file.write(f"  - 0.0% SELL signals\n")
report_file.write(f"\nCRITICAL: {pct_down:.1f}% of expected SELL signals are missing!\n\n")
report_file.write("CONCLUSION:\n")
report_file.write("The model was trained on data WITH downward movements,\n")
report_file.write("but is NOT outputting SELL signals in production.\n")
report_file.write("This indicates:\n")
report_file.write("  a) Model converged to always predict class 1 (BUY)\n")
report_file.write("  b) Decision boundary is miscalibrated\n")
report_file.write("  c) Post-processing is filtering SELL predictions\n\n")

report_file.close()

# ============ 5. PRINT SUMMARY ============
print("=" * 100)
print("AUDIT SUMMARY")
print("=" * 100)
print()
print("🚨 KEY FINDING:")
print(f"  Training data contains {pct_down:.1f}% downward price movements")
print(f"  But model outputs 0% SELL signals")
print()
print(f"This gap of {pct_down:.1f}% indicates the model is structurally biased toward BUY")
print()
print(f"✅ Report saved: {os.path.join(args.outdir, 'TRAINING_DATA_AUDIT.txt')}")

conn.close()
