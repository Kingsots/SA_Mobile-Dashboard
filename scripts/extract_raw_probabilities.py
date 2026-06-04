#!/usr/bin/env python3
"""
RAW PROBABILITY EXTRACTION - XGBOOST INFERENCE DIAGNOSTICS
Extract predict_proba() outputs for last 1,000 event-driven signals
Identify probability suppression mechanism
"""
import sqlite3
import json
from datetime import datetime, timedelta, timezone
import argparse
import os
from collections import defaultdict
import pickle
import logging
import sys

try:
    import pandas as pd
    import numpy as np
except ImportError:
    print("⚠️ pandas/numpy not available, using Python native structures")
    pd = None
    np = None

# Suppress XGBoost warnings if available
try:
    logging.getLogger('xgboost').setLevel(logging.ERROR)
except:
    pass

parser = argparse.ArgumentParser(description='Extract raw XGBoost probabilities')
parser.add_argument('--db', default='trading_bot.db', help='Database path')
parser.add_argument('--model', default='models/model_current.pkl', help='Model path')
parser.add_argument('--samples', type=int, default=1000, help='Number of samples')
parser.add_argument('--outdir', default='reports/probability_extraction', help='Output dir')
args = parser.parse_args()

os.makedirs(args.outdir, exist_ok=True)

conn = sqlite3.connect(args.db)
c = conn.cursor()

print("=" * 120)
print("RAW PROBABILITY EXTRACTION - XGBOOST INFERENCE DIAGNOSTICS")
print("=" * 120)
print(f"Database: {args.db}")
print(f"Model: {args.model}")
print(f"Samples: {args.samples}")
print()

# ============ LOAD MODEL ============
print("1. LOADING XGBOOST MODEL")
print("-" * 120)

try:
    with open(args.model, 'rb') as f:
        model_data = pickle.load(f)
        model = model_data.get('model') if isinstance(model_data, dict) else model_data
        print(f"✅ Model loaded: {type(model)}")
        print(f"   Classes: {model.classes_}")
        print(f"   N estimators: {model.n_estimators}")
except Exception as e:
    print(f"❌ Failed to load model: {e}")
    conn.close()
    raise SystemExit(1)

# ============ EXTRACT SIGNALS WITH FEATURES ============
print("\n2. EXTRACTING EVENT-DRIVEN SIGNALS WITH FEATURE SNAPSHOTS")
print("-" * 120)

c.execute("""
    SELECT id, timestamp, ticker, interval, signal, confidence, 
           model_version, triggered_by, feature_snapshot
    FROM ml_signals 
    WHERE triggered_by LIKE 'event:%' 
    ORDER BY timestamp DESC
    LIMIT ?
""", (args.samples,))

signals = c.fetchall()

if not signals:
    print("❌ No event-driven signals found!")
    conn.close()
    raise SystemExit(1)

print(f"✅ Extracted {len(signals)} event-driven signals")
print()

# ============ RE-RUN INFERENCE ============
print("3. RE-RUNNING INFERENCE ON HISTORICAL SIGNALS")
print("-" * 120)

signal_map = {1: 'BUY', -1: 'SELL', 0: 'NEUTRAL'}
results = []
inference_errors = 0
probabilities_class_0 = []
probabilities_class_1 = []

for idx, row in enumerate(signals):
    signal_id, timestamp, ticker, interval, signal, confidence, model_version, triggered_by, feature_snapshot = row
    
    try:
        # Parse feature snapshot
        if isinstance(feature_snapshot, str):
            features_dict = json.loads(feature_snapshot)
        else:
            features_dict = feature_snapshot
        
        # Create DataFrame with single row
        features_df = pd.DataFrame([features_dict])
        
        # Run inference
        predicted_class = model.predict(features_df)[0]
        predicted_proba = model.predict_proba(features_df)[0]
        
        # predicted_proba = [p_class_0, p_class_1] = [p_sell, p_buy]
        p_sell = float(predicted_proba[0])
        p_buy = float(predicted_proba[1])
        
        probabilities_class_0.append(p_sell)
        probabilities_class_1.append(p_buy)
        
        # Map class to signal
        class_to_signal_map = {0: -1, 1: 1}
        predicted_signal = class_to_signal_map.get(predicted_class, 0)
        predicted_signal_label = signal_map.get(predicted_signal, 'UNKNOWN')
        
        # Actual signal stored in database
        actual_signal_label = signal_map.get(signal, 'UNKNOWN')
        
        # Check if model prediction matches database
        match = "✓" if predicted_signal == signal else "✗"
        
        results.append({
            'timestamp': timestamp,
            'ticker': ticker,
            'event_type': triggered_by,
            'p_sell': p_sell,
            'p_buy': p_buy,
            'predicted_class': predicted_class,
            'predicted_signal': predicted_signal_label,
            'db_signal': actual_signal_label,
            'db_confidence': confidence,
            'match': match
        })
        
        if (idx + 1) % 100 == 0:
            print(f"  Processed {idx + 1}/{len(signals)} signals...")
    
    except Exception as e:
        inference_errors += 1
        if inference_errors <= 5:
            print(f"  ⚠️ Inference error on signal {signal_id}: {e}")

print(f"✅ Inference complete: {len(results)} successful, {inference_errors} errors")
print()

# ============ STATISTICAL SUMMARY ============
print("4. PROBABILITY DISTRIBUTION STATISTICS")
print("-" * 120)

if probabilities_class_0:
    p0_values = sorted(probabilities_class_0)
    p1_values = sorted(probabilities_class_1)
    
    # Calculate statistics
    p0_min = p0_values[0]
    p0_max = p0_values[-1]
    p0_mean = sum(p0_values) / len(p0_values)
    p0_median = p0_values[len(p0_values) // 2]
    p0_std = (sum((x - p0_mean) ** 2 for x in p0_values) / len(p0_values)) ** 0.5
    
    p1_min = p1_values[0]
    p1_max = p1_values[-1]
    p1_mean = sum(p1_values) / len(p1_values)
    p1_median = p1_values[len(p1_values) // 2]
    p1_std = (sum((x - p1_mean) ** 2 for x in p1_values) / len(p1_values)) ** 0.5
    
    print("Class 0 (SELL) Probabilities:")
    print(f"  Min:    {p0_min:.6f}")
    print(f"  Max:    {p0_max:.6f}")
    print(f"  Mean:   {p0_mean:.6f}")
    print(f"  Median: {p0_median:.6f}")
    print(f"  Std:    {p0_std:.6f}")
    print()
    
    print("Class 1 (BUY) Probabilities:")
    print(f"  Min:    {p1_min:.6f}")
    print(f"  Max:    {p1_max:.6f}")
    print(f"  Mean:   {p1_mean:.6f}")
    print(f"  Median: {p1_median:.6f}")
    print(f"  Std:    {p1_std:.6f}")
    print()

# ============ THRESHOLD ANALYSIS ============
print("5. THRESHOLD SENSITIVITY ANALYSIS")
print("-" * 120)

count_p0_gt_p1 = sum(1 for p in results if p['p_sell'] > p['p_buy'])
count_p0_gt_50 = sum(1 for p in results if p['p_sell'] > 0.5)
count_p0_gt_45 = sum(1 for p in results if p['p_sell'] > 0.45)
count_p0_gt_40 = sum(1 for p in results if p['p_sell'] > 0.4)
count_p0_gt_30 = sum(1 for p in results if p['p_sell'] > 0.3)

print(f"Count where p_sell > p_buy:     {count_p0_gt_p1} ({count_p0_gt_p1/len(results)*100:.1f}%)")
print(f"Count where p_sell > 0.50:      {count_p0_gt_50} ({count_p0_gt_50/len(results)*100:.1f}%)")
print(f"Count where p_sell > 0.45:      {count_p0_gt_45} ({count_p0_gt_45/len(results)*100:.1f}%)")
print(f"Count where p_sell > 0.40:      {count_p0_gt_40} ({count_p0_gt_40/len(results)*100:.1f}%)")
print(f"Count where p_sell > 0.30:      {count_p0_gt_30} ({count_p0_gt_30/len(results)*100:.1f}%)")
print()

# ============ HISTOGRAM / DISTRIBUTION ============
print("6. PROBABILITY DISTRIBUTION HISTOGRAM (10 BUCKETS)")
print("-" * 120)

# Manual histogram (10 buckets from 0 to 1)
bins = [i / 10 for i in range(11)]
hist_p0 = [0] * 10
hist_p1 = [0] * 10

for p in probabilities_class_0:
    bucket = int(p * 10)
    if bucket >= 10:
        bucket = 9
    hist_p0[bucket] += 1

for p in probabilities_class_1:
    bucket = int(p * 10)
    if bucket >= 10:
        bucket = 9
    hist_p1[bucket] += 1

print(f"{'Bucket':<12} {'Range':<15} {'p_sell Count':<15} {'p_buy Count':<15}")
print("-" * 120)
for i in range(len(bins) - 1):
    bucket_range = f"[{bins[i]:.2f}, {bins[i+1]:.2f})"
    print(f"{i:<12} {bucket_range:<15} {hist_p0[i]:<15} {hist_p1[i]:<15}")

print()

# ============ PREDICTION CORRECTNESS ============
print("7. MODEL PREDICTION VS DATABASE SIGNAL")
print("-" * 120)

match_count = sum(1 for r in results if r['match'] == '✓')
mismatch_count = len(results) - match_count

print(f"Model prediction matches database: {match_count}/{len(results)} ({match_count/len(results)*100:.1f}%)")
print(f"Model prediction differs:           {mismatch_count}/{len(results)} ({mismatch_count/len(results)*100:.1f}%)")
print()

# Show examples of mismatches
if mismatch_count > 0:
    print("Examples of mismatches (Model ≠ Database):")
    mismatch_examples = [r for r in results if r['match'] == '✗'][:5]
    for example in mismatch_examples:
        print(f"  {example['timestamp']} {example['ticker']}")
        print(f"    Model: {example['predicted_signal']} (p_sell={example['p_sell']:.4f}, p_buy={example['p_buy']:.4f})")
        print(f"    DB:    {example['db_signal']} (confidence={example['db_confidence']:.4f})")

print()

# ============ SIGNAL DISTRIBUTION ============
print("8. SIGNAL DISTRIBUTION COMPARISON")
print("-" * 120)

predicted_dist = defaultdict(int)
db_dist = defaultdict(int)

for r in results:
    predicted_dist[r['predicted_signal']] += 1
    db_dist[r['db_signal']] += 1

print(f"{'Signal':<10} {'Model Predict':<15} {'Database':<15}")
print("-" * 120)
for signal in ['BUY', 'SELL', 'NEUTRAL']:
    model_count = predicted_dist.get(signal, 0)
    db_count = db_dist.get(signal, 0)
    model_pct = (model_count / len(results) * 100) if results else 0
    db_pct = (db_count / len(results) * 100) if results else 0
    print(f"{signal:<10} {model_count:<5} ({model_pct:>5.1f}%)  {db_count:<5} ({db_pct:>5.1f}%)")

print()

# ============ WRITE CSV REPORT ============
print("9. WRITING DETAILED CSV REPORT")
print("-" * 120)

csv_path = os.path.join(args.outdir, 'raw_probabilities.csv')

# Write CSV manually
with open(csv_path, 'w') as f:
    # Header
    headers = ['timestamp', 'ticker', 'event_type', 'p_sell', 'p_buy', 'predicted_class', 'predicted_signal', 'db_signal', 'db_confidence', 'match']
    f.write(','.join(headers) + '\n')
    
    # Data rows
    for r in results:
        row = [
            r['timestamp'],
            r['ticker'],
            r['event_type'],
            f"{r['p_sell']:.6f}",
            f"{r['p_buy']:.6f}",
            str(r['predicted_class']),
            r['predicted_signal'],
            r['db_signal'],
            f"{r['db_confidence']:.4f}",
            r['match']
        ]
        f.write(','.join(row) + '\n')

print(f"✅ Saved: {csv_path}")
print()

# ============ WRITE TEXT REPORT ============
txt_path = os.path.join(args.outdir, 'PROBABILITY_EXTRACTION_REPORT.txt')
with open(txt_path, 'w') as f:
    f.write("=" * 120 + "\n")
    f.write("RAW PROBABILITY EXTRACTION REPORT\n")
    f.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n")
    f.write(f"Database: {args.db}\n")
    f.write(f"Model: {args.model}\n")
    f.write(f"Samples Analyzed: {len(results)}\n")
    f.write("=" * 120 + "\n\n")
    
    f.write("1. CLASS 0 (SELL) PROBABILITY STATISTICS\n")
    f.write("-" * 120 + "\n")
    if probabilities_class_0:
        p0_vals = sorted(probabilities_class_0)
        p0_m = sum(p0_vals) / len(p0_vals)
        f.write(f"Min:    {min(p0_vals):.6f}\n")
        f.write(f"Max:    {max(p0_vals):.6f}\n")
        f.write(f"Mean:   {p0_m:.6f}\n")
        f.write(f"Median: {p0_vals[len(p0_vals)//2]:.6f}\n")
        f.write(f"Std:    {(sum((x - p0_m)**2 for x in p0_vals) / len(p0_vals))**0.5:.6f}\n")
    f.write("\n")
    
    f.write("2. CLASS 1 (BUY) PROBABILITY STATISTICS\n")
    f.write("-" * 120 + "\n")
    if probabilities_class_1:
        p1_vals = sorted(probabilities_class_1)
        p1_m = sum(p1_vals) / len(p1_vals)
        f.write(f"Min:    {min(p1_vals):.6f}\n")
        f.write(f"Max:    {max(p1_vals):.6f}\n")
        f.write(f"Mean:   {p1_m:.6f}\n")
        f.write(f"Median: {p1_vals[len(p1_vals)//2]:.6f}\n")
        f.write(f"Std:    {(sum((x - p1_m)**2 for x in p1_vals) / len(p1_vals))**0.5:.6f}\n")
    f.write("\n")
    
    f.write("3. THRESHOLD ANALYSIS\n")
    f.write("-" * 120 + "\n")
    f.write(f"p_sell > p_buy:  {count_p0_gt_p1} ({count_p0_gt_p1/len(results)*100:.1f}%)\n")
    f.write(f"p_sell > 0.50:   {count_p0_gt_50} ({count_p0_gt_50/len(results)*100:.1f}%)\n")
    f.write(f"p_sell > 0.45:   {count_p0_gt_45} ({count_p0_gt_45/len(results)*100:.1f}%)\n")
    f.write(f"p_sell > 0.40:   {count_p0_gt_40} ({count_p0_gt_40/len(results)*100:.1f}%)\n")
    f.write(f"p_sell > 0.30:   {count_p0_gt_30} ({count_p0_gt_30/len(results)*100:.1f}%)\n")
    f.write("\n")
    
    f.write("4. PREDICTION CORRECTNESS\n")
    f.write("-" * 120 + "\n")
    f.write(f"Model matches database: {match_count}/{len(results)} ({match_count/len(results)*100:.1f}%)\n")
    f.write(f"Model differs:          {mismatch_count}/{len(results)} ({mismatch_count/len(results)*100:.1f}%)\n")
    f.write("\n")
    
    f.write("5. SIGNAL DISTRIBUTION\n")
    f.write("-" * 120 + "\n")
    f.write(f"{'Signal':<10} {'Model':<15} {'Database':<15}\n")
    f.write("-" * 120 + "\n")
    for signal in ['BUY', 'SELL', 'NEUTRAL']:
        model_count = predicted_dist.get(signal, 0)
        db_count = db_dist.get(signal, 0)
        f.write(f"{signal:<10} {model_count:<5} ({model_count/len(results)*100:>5.1f}%)  {db_count:<5} ({db_count/len(results)*100:>5.1f}%)\n")
    f.write("\n")
    
    f.write("6. ROOT CAUSE ANALYSIS\n")
    f.write("-" * 120 + "\n")
    
    if min(probabilities_class_0) < 0.15:
        f.write("FINDING: Class 0 (SELL) probabilities are extremely low (< 0.15)\n")
        f.write("DIAGNOSIS: Model has collapsed to always predict BUY\n")
        f.write("CAUSE: Training data imbalance or learning rate issue\n")
    elif count_p0_gt_p1 < 10:
        f.write("FINDING: p_sell never exceeds p_buy\n")
        f.write("DIAGNOSIS: Model is working correctly but confidently predicts BUY\n")
        f.write("CAUSE: Training data was actually imbalanced (BUY > SELL)\n")
    else:
        f.write("FINDING: p_sell is sometimes > p_buy but database shows 0 SELL\n")
        f.write("DIAGNOSIS: Post-processing threshold is suppressing SELL\n")
        f.write("CAUSE: Confidence filter or decision boundary is miscalibrated\n")

print(f"✅ Saved: {txt_path}")
print()

conn.close()

print("=" * 120)
print("PROBABILITY EXTRACTION COMPLETE")
print("=" * 120)
