#!/usr/bin/env python3
"""
PROBABILITY ANALYSIS WITHOUT MODEL RELOAD
Since model probabilities aren't directly stored, analyze pattern of predictions
"""
import sqlite3
import json
from datetime import datetime, timedelta, timezone
import argparse
import os
from collections import defaultdict

parser = argparse.ArgumentParser(description='Analyze signal prediction patterns')
parser.add_argument('--db', default='trading_bot.db', help='Database path')
parser.add_argument('--samples', type=int, default=1000, help='Number of samples')
parser.add_argument('--outdir', default='reports/probability_analysis', help='Output dir')
args = parser.parse_args()

os.makedirs(args.outdir, exist_ok=True)

conn = sqlite3.connect(args.db)
c = conn.cursor()

print("=" * 120)
print("PROBABILITY ANALYSIS - INFERENCE PATTERN DIAGNOSTICS")
print("=" * 120)
print(f"Database: {args.db}")
print(f"Samples: {args.samples}")
print()

# ============ LOAD SIGNALS ============
print("1. EXTRACTING EVENT-DRIVEN SIGNALS")
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

# ============ ANALYZE CONFIDENCE PATTERNS ============
print("2. CONFIDENCE PATTERN ANALYSIS")
print("-" * 120)

signal_map = {1: 'BUY', -1: 'SELL', 0: 'NEUTRAL'}
signal_dist = defaultdict(lambda: {'count': 0, 'sum_conf': 0, 'min_conf': 1.0, 'max_conf': 0.0})
confidence_buckets = defaultdict(lambda: {'buy': 0, 'sell': 0, 'neutral': 0})

for row in signals:
    signal_id, timestamp, ticker, interval, signal, confidence, model_version, triggered_by, feature_snapshot = row
    
    signal_label = signal_map.get(signal, 'UNKNOWN')
    signal_dist[signal_label]['count'] += 1
    signal_dist[signal_label]['sum_conf'] += confidence
    signal_dist[signal_label]['min_conf'] = min(signal_dist[signal_label]['min_conf'], confidence)
    signal_dist[signal_label]['max_conf'] = max(signal_dist[signal_label]['max_conf'], confidence)
    
    # Bin confidence into buckets
    conf_bucket = int(confidence * 10)
    if conf_bucket >= 10:
        conf_bucket = 9
    confidence_buckets[conf_bucket][signal_label.lower()] += 1

print(f"{'Signal':<10} {'Count':<8} {'Mean Conf':<12} {'Min Conf':<12} {'Max Conf':<12}")
print("-" * 120)

for direction in ['BUY', 'SELL', 'NEUTRAL']:
    stats = signal_dist[direction]
    if stats['count'] > 0:
        mean_conf = stats['sum_conf'] / stats['count']
        print(f"{direction:<10} {stats['count']:<8} {mean_conf:>11.4f}  {stats['min_conf']:>11.4f}  {stats['max_conf']:>11.4f}")
    else:
        print(f"{direction:<10} {0:<8} {'N/A':>11}  {'N/A':>11}  {'N/A':>11}")

print()

# ============ CONFIDENCE DISTRIBUTION ============
print("3. CONFIDENCE DISTRIBUTION HISTOGRAM (10 BUCKETS)")
print("-" * 120)

print(f"{'Bucket':<12} {'Range':<15} {'BUY':<10} {'SELL':<10} {'NEUTRAL':<10}")
print("-" * 120)

for bucket in range(10):
    range_start = bucket / 10
    range_end = (bucket + 1) / 10
    bucket_range = f"[{range_start:.1f}, {range_end:.1f})"
    
    counts = confidence_buckets[bucket]
    print(f"{bucket:<12} {bucket_range:<15} {counts['buy']:<10} {counts['sell']:<10} {counts['neutral']:<10}")

print()

# ============ FEATURE ANALYSIS ============
print("4. FEATURE SNAPSHOT ANALYSIS (Sample)")
print("-" * 120)

# Parse one feature snapshot to see what features are available
for row in signals[:1]:
    feature_snapshot = row[8]
    try:
        if isinstance(feature_snapshot, str):
            features = json.loads(feature_snapshot)
        else:
            features = feature_snapshot
        
        print(f"Available features ({len(features)} total):")
        feature_list = sorted(features.keys())[:10]  # Show first 10
        for feat in feature_list:
            print(f"  - {feat}: {features[feat]}")
        if len(features) > 10:
            print(f"  ... and {len(features) - 10} more")
    except Exception as e:
        print(f"Could not parse features: {e}")

print()

# ============ CRITICAL FINDING ============
print("5. CRITICAL FINDING")
print("-" * 120)

total = len(signals)
sell_count = signal_dist['SELL']['count']
buy_count = signal_dist['BUY']['count']
neutral_count = signal_dist['NEUTRAL']['count']

print(f"Total signals analyzed: {total}")
print(f"  BUY:     {buy_count} ({buy_count/total*100:.1f}%)")
print(f"  SELL:    {sell_count} ({sell_count/total*100:.1f}%)")
print(f"  NEUTRAL: {neutral_count} ({neutral_count/total*100:.1f}%)")
print()

if sell_count == 0:
    print("🚨 CRITICAL: ZERO SELL SIGNALS")
    print()
    print("This confirms the model is NOT outputting SELL class (0)")
    print("Evidence:")
    print(f"  1. {total} event-driven signals analyzed")
    print(f"  2. 0 SELL signals in entire dataset")
    print(f"  3. This is NOT a statistical anomaly (0% is impossible)")
    print()
    print("Root cause is one of:")
    print("  A) Model.predict() never returns class 0")
    print("  B) Post-processing filters out all class 0 predictions")
    print("  C) Signal written to database has all SELL signals stripped")
    print()
    print("To diagnose further, we need to:")
    print("  1. Load raw model and test predict_proba()")
    print("  2. Add logging to predict_signal() method")
    print("  3. Check if joblib.load() can access model directly")

# ============ WRITE REPORT ============
print()
print("6. WRITING ANALYSIS REPORT")
print("-" * 120)

report_path = os.path.join(args.outdir, 'INFERENCE_PATTERN_REPORT.txt')

with open(report_path, 'w') as f:
    f.write("=" * 120 + "\n")
    f.write("INFERENCE PATTERN ANALYSIS REPORT\n")
    f.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n")
    f.write(f"Database: {args.db}\n")
    f.write("=" * 120 + "\n\n")
    
    f.write("CRITICAL OBSERVATION\n")
    f.write("-" * 120 + "\n")
    f.write(f"Total Signals: {total}\n")
    f.write(f"BUY:    {buy_count} ({buy_count/total*100:.1f}%)\n")
    f.write(f"SELL:   {sell_count} ({sell_count/total*100:.1f}%)\n")
    f.write(f"NEUTRAL: {neutral_count} ({neutral_count/total*100:.1f}%)\n\n")
    
    if sell_count == 0:
        f.write("🚨 CONFIRMED: ZERO SELL SIGNALS IN {total} PREDICTIONS\n\n")
        f.write("This is not a statistical variance - it's a systematic defect.\n\n")
        f.write("The model's predict() method is NOT returning class 0 (SELL).\n\n")
        f.write("Next steps:\n")
        f.write("  1. Check XGBoost model classes: confirmed? 0 and 1 only?\n")
        f.write("  2. Extract raw probabilities with predict_proba()\n")
        f.write("  3. Verify decision boundary: argmax always returns 1?\n")
        f.write("  4. Check if retrain needed with balanced class_weight\n")
    
    f.write("\nConfidence statistics:\n\n")
    for direction in ['BUY', 'SELL', 'NEUTRAL']:
        stats = signal_dist[direction]
        if stats['count'] > 0:
            mean_conf = stats['sum_conf'] / stats['count']
            f.write(f"{direction}:\n")
            f.write(f"  Count: {stats['count']}\n")
            f.write(f"  Mean Confidence: {mean_conf:.4f}\n")
            f.write(f"  Min:  {stats['min_conf']:.4f}\n")
            f.write(f"  Max:  {stats['max_conf']:.4f}\n\n")

print(f"✅ Report saved: {report_path}")

conn.close()

print()
print("=" * 120)
print("ANALYSIS COMPLETE")
print("=" * 120)
