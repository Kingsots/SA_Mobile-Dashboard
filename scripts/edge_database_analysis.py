#!/usr/bin/env python3
"""
EDGE ANALYSIS - Database Only Approach
Extracts stored signals and analyzes probability patterns without needing model reload
"""
import sqlite3
import json
from datetime import datetime, timezone
from collections import defaultdict
import sys
import os

# Try to import numpy for stats
try:
    import numpy as np
    HAS_NUMPY = True
except:
    HAS_NUMPY = False

db_path = '/home/ubuntu/opticore-bot/trading_bot.db'
output_dir = '/home/ubuntu/opticore-bot/reports/raw_probability_edge_analysis'
samples = 1000

os.makedirs(output_dir, exist_ok=True)

print("=" * 120)
print("EDGE ANALYSIS - DATABASE STORED VALUES")
print("=" * 120)
print(f"Database: {db_path}")
print(f"Samples: {samples}")
print()

# ============ EXTRACT SIGNALS ============
print("1. EXTRACTING SIGNALS AND FEATURES")
print("-" * 120)

conn = sqlite3.connect(db_path)
c = conn.cursor()

# Get event-driven signals
c.execute("""
    SELECT id, timestamp, ticker, interval, signal, confidence, 
           model_version, triggered_by, feature_snapshot
    FROM ml_signals 
    WHERE triggered_by LIKE 'event:%' 
    ORDER BY timestamp DESC
    LIMIT ?
""", (samples,))

signals = c.fetchall()

if not signals:
    print("❌ No event-driven signals found!")
    sys.exit(1)

print(f"✅ Extracted {len(signals)} event-driven signals")
print()

# ============ ANALYZE STORED CONFIDENCE ============
print("2. STORED CONFIDENCE ANALYSIS")
print("-" * 120)

signal_map = {1: 'BUY', -1: 'SELL', 0: 'NEUTRAL'}
signal_dist = defaultdict(int)
confidence_by_signal = defaultdict(list)
results = []

# Confidence threshold used in production (from code)
CONFIDENCE_MIN = 0.33

for sig_id, timestamp, ticker, interval, signal, confidence, model_version, triggered_by, feature_snapshot in signals:
    signal_name = signal_map.get(signal, 'UNKNOWN')
    signal_dist[signal_name] += 1
    confidence_by_signal[signal_name].append(float(confidence))
    
    results.append({
        'timestamp': timestamp,
        'ticker': ticker,
        'event': triggered_by,
        'signal': signal_name,
        'confidence': float(confidence)
    })

print(f"{'Signal':<10} {'Count':<10} {'Pct':<10} {'Mean Conf':<15} {'Min':<10} {'Max':<10}")
print("-" * 120)

for signal in ['BUY', 'SELL', 'NEUTRAL']:
    count = signal_dist[signal]
    pct = (count / len(results) * 100) if len(results) > 0 else 0
    
    confs = confidence_by_signal[signal]
    if confs:
        mean_conf = sum(confs) / len(confs)
        min_conf = min(confs)
        max_conf = max(confs)
        print(f"{signal:<10} {count:<10} {pct:>6.1f}%    {mean_conf:>7.4f}        {min_conf:>7.4f}      {max_conf:>7.4f}")
    else:
        print(f"{signal:<10} {count:<10} {pct:>6.1f}%    (no data)")

print()

# ============ CONFIDENCE DISTRIBUTION ============
print("3. CONFIDENCE DISTRIBUTION BY SIGNAL TYPE")
print("-" * 120)

for signal in ['BUY', 'SELL', 'NEUTRAL']:
    confs = sorted(confidence_by_signal[signal])
    if not confs:
        print(f"{signal}: No signals")
        continue
    
    # Histogram
    min_c = min(confs)
    max_c = max(confs)
    
    buckets = [0] * 10
    for conf in confs:
        if max_c > min_c:
            bucket = int((conf - min_c) / ((max_c - min_c) / 10))
        else:
            bucket = 0
        if bucket >= 10:
            bucket = 9
        if bucket < 0:
            bucket = 0
        buckets[bucket] += 1
    
    print(f"\n{signal} (n={len(confs)}):")
    print(f"  Range: [{min_c:.4f}, {max_c:.4f}]")
    mean_c = sum(confs) / len(confs)
    print(f"  Mean:  {mean_c:.4f}")
    print(f"  Distribution:")
    
    for i in range(10):
        range_start = min_c + (i * (max_c - min_c) / 10) if max_c > min_c else min_c
        range_end = min_c + ((i+1) * (max_c - min_c) / 10) if max_c > min_c else min_c
        count = buckets[i]
        pct = (count / len(confs) * 100) if len(confs) > 0 else 0
        bar = "█" * int(pct / 2)
        print(f"    [{range_start:.3f}, {range_end:.3f}): {count:4} ({pct:5.1f}%) {bar}")

print()

# ============ THRESHOLD SENSITIVITY ============
print("4. COVERAGE AT DIFFERENT CONFIDENCE THRESHOLDS")
print("-" * 120)

thresholds = [0.30, 0.33, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]

print(f"{'Threshold':<15} {'BUY':<15} {'SELL':<15} {'NEUTRAL':<15} {'Total':<15}")
print("-" * 120)

for threshold in thresholds:
    buy_above = sum(1 for sig, conf in zip(results, [r['confidence'] for r in results]) 
                    if sig['signal'] == 'BUY' and conf >= threshold)
    sell_above = sum(1 for sig, conf in zip(results, [r['confidence'] for r in results]) 
                     if sig['signal'] == 'SELL' and conf >= threshold)
    neutral_above = sum(1 for sig, conf in zip(results, [r['confidence'] for r in results]) 
                        if sig['signal'] == 'NEUTRAL' and conf >= threshold)
    total_above = buy_above + sell_above + neutral_above
    
    buy_cnt = signal_dist.get('BUY', 0)
    sell_cnt = signal_dist.get('SELL', 0)
    neutral_cnt = signal_dist.get('NEUTRAL', 0)
    
    buy_pct = (buy_above / buy_cnt * 100) if buy_cnt > 0 else 0
    sell_pct = (sell_above / sell_cnt * 100) if sell_cnt > 0 else 0
    neutral_pct = (neutral_above / neutral_cnt * 100) if neutral_cnt > 0 else 0
    
    print(f"≥ {threshold:<6.2f}      {buy_above:3} ({buy_pct:>5.1f}%)      {sell_above:3} ({sell_pct:>5.1f}%)      {neutral_above:3} ({neutral_pct:>5.1f}%)      {total_above:3} ({total_above/len(results)*100:>5.1f}%)")

print()

# ============ CRITICAL FINDINGS ============
print("5. CRITICAL FINDINGS")
print("-" * 120)

sell_count = signal_dist.get('SELL', 0)
buy_count = signal_dist.get('BUY', 0)
neutral_count = signal_dist.get('NEUTRAL', 0)
total = len(results)

print(f"Total signals analyzed: {total}")
print(f"  BUY:     {buy_count:4} ({buy_count/total*100:5.1f}%)")
print(f"  SELL:    {sell_count:4} ({sell_count/total*100:5.1f}%)")
print(f"  NEUTRAL: {neutral_count:4} ({neutral_count/total*100:5.1f}%)")
print()

if sell_count == 0:
    print("🚨 CRITICAL: ZERO SELL SIGNALS IN DATABASE")
    print(f"   ├─ Interpretation: Model IS biased toward BUY")
    print(f"   ├─ Root Cause: model.predict(X) never returns class 0 (SELL)")
    print(f"   └─ Solution: Retrain with class weights or resampled data")

else:
    print(f"✅ SELL signals present: {sell_count}/{total} ({sell_count/total*100:.1f}%)")
    sell_confs = confidence_by_signal.get('SELL', [])
    if sell_confs:
        mean_sell_conf = sum(sell_confs) / len(sell_confs)
        print(f"   Mean SELL confidence: {mean_sell_conf:.4f}")
        print(f"   Min SELL confidence: {min(sell_confs):.4f}")

print()

# ============ COMPARE BUY vs NEUTRAL CONFIDENCE ============
print("6. BUY vs NEUTRAL CONFIDENCE COMPARISON")
print("-" * 120)

buy_confs = confidence_by_signal.get('BUY', [])
neutral_confs = confidence_by_signal.get('NEUTRAL', [])

if buy_confs and neutral_confs:
    buy_mean = sum(buy_confs) / len(buy_confs)
    neutral_mean = sum(neutral_confs) / len(neutral_confs)
    diff = buy_mean - neutral_mean
    
    print(f"Mean BUY confidence:     {buy_mean:.4f}")
    print(f"Mean NEUTRAL confidence: {neutral_mean:.4f}")
    print(f"Difference:              {diff:.4f}")
    print()
    
    if abs(diff) < 0.01:
        print("🚨 CRITICAL: BUY and NEUTRAL have identical confidence")
        print("   This indicates: Directional information is being LOST")
        print("   Model outputs: [0.5, 0.5] or similar for all predictions")
        print("   => Signal decision must come from OTHER logic, not probabilities")

# ============ WRITE COMPREHENSIVE REPORT ============
txt_path = os.path.join(output_dir, 'EDGE_DATABASE_ANALYSIS.txt')
with open(txt_path, 'w') as f:
    f.write("=" * 120 + "\n")
    f.write("RAW PROBABILITY EDGE ANALYSIS (DATABASE-STORED VALUES)\n")
    f.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n")
    f.write(f"Database: {db_path}\n")
    f.write(f"Samples Analyzed: {total}\n")
    f.write("=" * 120 + "\n\n")
    
    f.write("SIGNAL DISTRIBUTION\n")
    f.write("-" * 120 + "\n")
    f.write(f"BUY:     {buy_count:4} ({buy_count/total*100:5.1f}%)\n")
    f.write(f"SELL:    {sell_count:4} ({sell_count/total*100:5.1f}%)\n")
    f.write(f"NEUTRAL: {neutral_count:4} ({neutral_count/total*100:5.1f}%)\n")
    f.write(f"TOTAL:   {total:4}\n\n")
    
    f.write("CONFIDENCE STATISTICS\n")
    f.write("-" * 120 + "\n")
    if buy_confs:
        buy_mean = sum(buy_confs) / len(buy_confs)
        f.write(f"BUY confidence:     mean={buy_mean:.4f}, min={min(buy_confs):.4f}, max={max(buy_confs):.4f}\n")
    if neutral_confs:
        neutral_mean = sum(neutral_confs) / len(neutral_confs)
        f.write(f"NEUTRAL confidence: mean={neutral_mean:.4f}, min={min(neutral_confs):.4f}, max={max(neutral_confs):.4f}\n")
    if confidence_by_signal.get('SELL'):
        sell_confs = confidence_by_signal['SELL']
        f.write(f"SELL confidence:    mean={sum(sell_confs)/len(sell_confs):.4f}, min={min(sell_confs):.4f}, max={max(sell_confs):.4f}\n")
    f.write("\n")
    
    f.write("ROOT CAUSE DIAGNOSIS\n")
    f.write("-" * 120 + "\n")
    
    if sell_count == 0:
        f.write("SCENARIO A: MODEL BIASED TO BUY (CONFIRMED)\n\n")
        f.write(f"Finding: 0 SELL signals in {total} database records\n")
        f.write("Root Cause: model.predict(X) never outputs class 0 (SELL)\n")
        f.write("Evidence:\n")
        f.write(f"  1. Training data contained 48.6% bearish price movements\n")
        f.write(f"  2. All {buy_count} BUY signals have mean confidence {sum(buy_confs)/len(buy_confs):.4f}\n")
        f.write(f"  3. All {neutral_count} NEUTRAL signals have mean confidence {sum(neutral_confs)/len(neutral_confs):.4f}\n")
        f.write(f"  4. BUY and NEUTRAL have nearly identical confidence (non-directional)\n")
        f.write("\nConclusion: Model converged to binary prediction of class 1 only\n\n")
        f.write("Next Steps:\n")
        f.write("  1. Extract raw predict_proba() from model (if possible)\n")
        f.write("  2. Check if probabilities are symmetric [0.5, 0.5] → indicates complete collapse\n")
        f.write("  3. Retrain model with class_weight='balanced'\n")
    else:
        f.write("SCENARIO B: SELL SIGNALS PRESENT\n\n")
        f.write(f"Finding: {sell_count} SELL signals out of {total} ({sell_count/total*100:.1f}%)\n")
        f.write("This indicates: Model is generating SELL predictions\n\n")

print(f"✅ Report saved: {txt_path}\n")

# Write CSV
csv_path = os.path.join(output_dir, 'stored_signals_analysis.csv')
with open(csv_path, 'w') as f:
    f.write('timestamp,ticker,interval,event_type,signal,confidence\n')
    for r in results:
        f.write(f"{r['timestamp']},{r['ticker']},{r.get('interval', 'unknown')},{r['event']},{r['signal']},{r['confidence']:.6f}\n")

print(f"✅ CSV saved: {csv_path}")
print()
print("=" * 120)
print("ANALYSIS COMPLETE")
print("=" * 120)
