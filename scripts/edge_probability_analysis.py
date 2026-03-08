#!/usr/bin/env python3
"""
RAW PROBABILITY EXTRACTION WITH EDGE ANALYSIS
Extract predict_proba() outputs directly and analyze probability spread
"""
import sqlite3
import json
import pickle
import os
import sys
from datetime import datetime, timezone
from collections import defaultdict

parser_import = False
try:
    import argparse
    parser_import = True
except:
    pass

if parser_import:
    import argparse
    parser = argparse.ArgumentParser(description='Extract raw probabilities and analyze edge')
    parser.add_argument('--db', default='trading_bot.db', help='Database path')
    parser.add_argument('--model', default='/home/ubuntu/opticore-bot/data/models/model_current.pkl', help='Model path')
    parser.add_argument('--samples', type=int, default=500, help='Number of samples')
    parser.add_argument('--outdir', default='reports/raw_probability_edge_analysis', help='Output dir')
    args = parser.parse_args()
else:
    class Args:
        db = 'trading_bot.db'
        model = '/home/ubuntu/opticore-bot/data/models/model_current.pkl'
        samples = 500
        outdir = 'reports/raw_probability_edge_analysis'
    args = Args()

os.makedirs(args.outdir, exist_ok=True)

print("=" * 120)
print("RAW PROBABILITY EXTRACTION - EDGE ANALYSIS")
print("=" * 120)
print(f"Database: {args.db}")
print(f"Model: {args.model}")
print(f"Samples: {args.samples}")
print()

# ============ LOAD MODEL WITH JOBLIB ============
print("1. LOADING XGBOOST MODEL")
print("-" * 120)

model = None

# Try joblib first (native XGBoost save format)
try:
    import joblib
    try:
        model = joblib.load(args.model)
        print(f"✅ Model loaded via joblib")
        print(f"   Type: {type(model)}")
        print(f"   Classes: {model.classes_}")
        print(f"   N estimators: {model.n_estimators}")
    except Exception as e:
        print(f"⚠️ joblib.load() failed: {e}")
except:
    print("⚠️ joblib not available")

# Try pickle as fallback
if model is None:
    try:
        with open(args.model, 'rb') as f:
            data = pickle.load(f)
        
        if isinstance(data, dict) and 'model' in data:
            model = data['model']
        else:
            model = data
        
        print(f"✅ Model loaded via pickle")
        print(f"   Type: {type(model)}")
        print(f"   Classes: {model.classes_}")
        print(f"   N estimators: {model.n_estimators}")
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if model is None:
    print(f"❌ Could not load model from {args.model}")
    sys.exit(1)

print()

# ============ LOAD DATABASE ============
print("2. EXTRACTING SIGNALS AND FEATURES")
print("-" * 120)

conn = sqlite3.connect(args.db)
c = conn.cursor()

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
    sys.exit(1)

print(f"✅ Extracted {len(signals)} event-driven signals")
print()

# ============ RUN INFERENCE AND EXTRACT PROBABILITIES ============
print("3. EXTRACTING RAW PROBABILITIES")
print("-" * 120)

signal_map = {1: 'BUY', -1: 'SELL', 0: 'NEUTRAL'}
p_buy_list = []
p_sell_list = []
edge_list = []
results = []
inference_count = 0
errors = 0

for idx, row in enumerate(signals):
    signal_id, timestamp, ticker, interval, signal, confidence, model_version, triggered_by, feature_snapshot = row
    
    try:
        # Parse feature snapshot
        if isinstance(feature_snapshot, str):
            features_dict = json.loads(feature_snapshot)
        else:
            features_dict = feature_snapshot
        
        # Convert dict to list in correct order for model
        try:
            # Get feature names from model
            feature_names = model.get_booster().feature_names
            if feature_names is None:
                # Use keys from dict if no metadata
                feature_names = sorted(features_dict.keys())
            
            # Extract features in order
            X_values = [float(features_dict.get(fname, 0.0)) for fname in feature_names]
        except:
            # Fallback: just use dict values
            X_values = [float(v) for v in features_dict.values()]
        
        # Reshape for single sample
        X_sample = [[float(x) for x in X_values]]
        
        # Get probabilities
        probas = model.predict_proba(X_sample)[0]
        
        # probas = [p_class_0, p_class_1] = [p_sell, p_buy]
        p_sell = float(probas[0])
        p_buy = float(probas[1])
        edge = p_buy - p_sell
        
        p_buy_list.append(p_buy)
        p_sell_list.append(p_sell)
        edge_list.append(edge)
        
        # Get predicted class
        predicted_class = model.predict([X_values])[0]
        predicted_signal = signal_map.get({0: -1, 1: 1}.get(predicted_class, 0), 'UNKNOWN')
        actual_signal = signal_map.get(signal, 'UNKNOWN')
        
        results.append({
            'timestamp': timestamp,
            'ticker': ticker,
            'event_type': triggered_by,
            'p_sell': p_sell,
            'p_buy': p_buy,
            'edge': edge,
            'predicted_signal': predicted_signal,
            'actual_signal': actual_signal,
            'db_confidence': confidence
        })
        
        inference_count += 1
        
        if (idx + 1) % 100 == 0:
            print(f"  Processed {idx + 1}/{len(signals)}...")
    
    except Exception as e:
        errors += 1
        if errors <= 3:
            print(f"  ⚠️ Error on signal {signal_id}: {str(e)[:80]}")

print(f"✅ Inference complete: {inference_count} successful, {errors} errors")
print()

# ============ PROBABILITY STATISTICS ============
print("4. PROBABILITY STATISTICS")
print("-" * 120)

if p_buy_list:
    p_buy_mean = sum(p_buy_list) / len(p_buy_list)
    p_buy_min = min(p_buy_list)
    p_buy_max = max(p_buy_list)
    
    p_sell_mean = sum(p_sell_list) / len(p_sell_list)
    p_sell_min = min(p_sell_list)
    p_sell_max = max(p_sell_list)
    
    edge_mean = sum(edge_list) / len(edge_list)
    edge_min = min(edge_list)
    edge_max = max(edge_list)
    
    print(f"Mean p_buy:  {p_buy_mean:.4f}")
    print(f"Mean p_sell: {p_sell_mean:.4f}")
    print(f"Mean edge:   {edge_mean:.4f}")
    print()
    print(f"p_buy range:  [{p_buy_min:.4f}, {p_buy_max:.4f}]")
    print(f"p_sell range: [{p_sell_min:.4f}, {p_sell_max:.4f}]")
    print(f"Edge range:   [{edge_min:.4f}, {edge_max:.4f}]")
    print()

# ============ THRESHOLD ANALYSIS ============
print("5. THRESHOLD SENSITIVITY ANALYSIS")
print("-" * 120)

# Count predictions at different edge thresholds
edge_thresholds = [-0.2, -0.15, -0.1, -0.08, -0.05, 0.0, 0.05, 0.08]

print(f"Latent SELL signals (where p_sell > p_buy):")
latent_sell = sum(1 for e in edge_list if e < 0)
print(f"  Total: {latent_sell} ({latent_sell/len(edge_list)*100:.1f}%)")
print()

print(f"SELL signals by edge threshold:")
for threshold in edge_thresholds:
    count = sum(1 for e in edge_list if e < threshold)
    pct = (count / len(edge_list) * 100) if len(edge_list) > 0 else 0
    print(f"  edge < {threshold:6.2f}: {count:4} ({pct:5.1f}%)")

print()

# ============ DISTRIBUTION ANALYSIS ============
print("6. EDGE DISTRIBUTION (10 BUCKETS)")
print("-" * 120)

# Manual histogram for edge values
min_edge = min(edge_list)
max_edge = max(edge_list)
bucket_size = (max_edge - min_edge) / 10 if max_edge > min_edge else 1.0

buckets = [0] * 10
for edge in edge_list:
    bucket = int((edge - min_edge) / bucket_size) if bucket_size > 0 else 0
    if bucket >= 10:
        bucket = 9
    if bucket < 0:
        bucket = 0
    buckets[bucket] += 1

print(f"{'Bucket':<8} {'Range':<30} {'Count':<8} {'Pct':<8}")
print("-" * 120)
for i in range(10):
    range_start = min_edge + (i * bucket_size)
    range_end = min_edge + ((i + 1) * bucket_size)
    count = buckets[i]
    pct = (count / len(edge_list) * 100) if len(edge_list) > 0 else 0
    print(f"{i:<8} [{range_start:7.4f}, {range_end:7.4f})  {count:<8} {pct:>6.1f}%")

print()

# ============ PREDICTION CORRECTNESS ============
print("7. PREDICTION VS DATABASE MATCH")
print("-" * 120)

matches = sum(1 for r in results if r['predicted_signal'] == r['actual_signal'])
print(f"Model predictions match database: {matches}/{len(results)} ({matches/len(results)*100:.1f}%)")
print()

# Show distribution
pred_dist = defaultdict(int)
db_dist = defaultdict(int)
for r in results:
    pred_dist[r['predicted_signal']] += 1
    db_dist[r['actual_signal']] += 1

print(f"{'Signal':<10} {'Model':<15} {'Database':<15}")
print("-" * 120)
for signal in ['BUY', 'SELL', 'NEUTRAL']:
    model_count = pred_dist.get(signal, 0)
    db_count = db_dist.get(signal, 0)
    print(f"{signal:<10} {model_count:<5} ({model_count/len(results)*100:>5.1f}%)  {db_count:<5} ({db_count/len(results)*100:>5.1f}%)")

print()

# ============ CRITICAL FINDINGS ============
print("8. CRITICAL FINDINGS")
print("-" * 120)

latent_sell_count = sum(1 for e in edge_list if e < 0)
latent_sell_strong = sum(1 for e in edge_list if e < -0.08)
latent_sell_threshold_10 = sum(1 for e in edge_list if e < -0.1)

print(f"Latent SELL signals detected (p_sell > p_buy): {latent_sell_count}")
print(f"Strong latent SELL (edge < -0.08): {latent_sell_strong}")
print(f"Very strong latent SELL (edge < -0.1): {latent_sell_threshold_10}")
print()

if latent_sell_count > 0:
    print(f"🚨 CRITICAL: Model IS generating SELL probabilities but they're being suppressed!")
    print(f"   {latent_sell_count} out of {len(results)} signals have p_sell > p_buy")
    print(f"   This means: Decision boundary OR post-processing is filtering them out")
else:
    print(f"🚨 CRITICAL: Model has NO latent SELL signals")
    print(f"   p_sell IS NEVER greater than p_buy")
    print(f"   This means: Model completely collapsed to BUY-only")

print()

# ============ WRITE REPORT ============
print("9. WRITING DETAILED REPORT")
print("-" * 120)

txt_path = os.path.join(args.outdir, 'EDGE_ANALYSIS_REPORT.txt')

with open(txt_path, 'w') as f:
    f.write("=" * 120 + "\n")
    f.write("RAW PROBABILITY EDGE ANALYSIS REPORT\n")
    f.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n")
    f.write(f"Database: {args.db}\n")
    f.write(f"Model: {args.model}\n")
    f.write(f"Samples Analyzed: {len(results)}\n")
    f.write("=" * 120 + "\n\n")
    
    f.write("PROBABILITY STATISTICS\n")
    f.write("-" * 120 + "\n")
    if p_buy_list:
        f.write(f"Mean p_buy:  {p_buy_mean:.4f}\n")
        f.write(f"Mean p_sell: {p_sell_mean:.4f}\n")
        f.write(f"Mean edge:   {edge_mean:.4f}\n\n")
        f.write(f"p_buy range:  [{p_buy_min:.4f}, {p_buy_max:.4f}]\n")
        f.write(f"p_sell range: [{p_sell_min:.4f}, {p_sell_max:.4f}]\n")
        f.write(f"Edge range:   [{edge_min:.4f}, {edge_max:.4f}]\n\n")
    
    f.write("LATENT SELL ANALYSIS\n")
    f.write("-" * 120 + "\n")
    f.write(f"Total signals with p_sell > p_buy (latent SELL): {latent_sell_count} ({latent_sell_count/len(results)*100:.1f}%)\n")
    f.write(f"Strong latent SELL (edge < -0.08): {latent_sell_strong}\n")
    f.write(f"Very strong latent SELL (edge < -0.1): {latent_sell_threshold_10}\n\n")
    
    f.write("ROOT CAUSE DIAGNOSIS\n")
    f.write("-" * 120 + "\n")
    
    if latent_sell_count == 0:
        f.write("SCENARIO A: MODEL COMPLETELY COLLAPSED TO BUY-ONLY\n\n")
        f.write("Finding: p_sell is NEVER greater than p_buy\n")
        f.write("Diagnosis: Model has completely failed to learn SELL class\n")
        f.write("Cause: Training data imbalance or learning failure\n")
        f.write("Fix: Retrain with balanced class_weight or resampled data\n")
    
    elif latent_sell_count < len(results) * 0.05:
        f.write("SCENARIO B: RARE LATENT SELL (< 5%)\n\n")
        f.write(f"Finding: Only {latent_sell_count} out of {len(results)} have p_sell > p_buy\n")
        f.write("Diagnosis: Model heavily biased toward BUY\n")
        f.write("Cause: Class imbalance in training data\n")
        f.write("Fix: Use class_weight='balanced' and retrain\n")
    
    else:
        f.write("SCENARIO C: SIGNIFICANT LATENT SELL DETECTED\n\n")
        f.write(f"Finding: {latent_sell_count} signals have p_sell > p_buy ({latent_sell_count/len(results)*100:.1f}%)\n")
        f.write("Diagnosis: Model IS learning SELL but threshold/post-processing suppresses it\n")
        f.write("Cause: Decision boundary miscalibrated OR confidence filter too strict\n")
        f.write("Fix: Adjust decision boundary or lower SELL confidence threshold\n")

print(f"✅ Report saved: {txt_path}")

# Write CSV with detailed results
csv_path = os.path.join(args.outdir, 'raw_probabilities_with_edge.csv')
with open(csv_path, 'w') as f:
    headers = ['timestamp', 'ticker', 'event_type', 'p_sell', 'p_buy', 'edge', 'predicted_signal', 'actual_signal', 'db_confidence']
    f.write(','.join(headers) + '\n')
    for r in results:
        row = [
            r['timestamp'],
            r['ticker'],
            r['event_type'],
            f"{r['p_sell']:.6f}",
            f"{r['p_buy']:.6f}",
            f"{r['edge']:.6f}",
            r['predicted_signal'],
            r['actual_signal'],
            f"{r['db_confidence']:.4f}"
        ]
        f.write(','.join(row) + '\n')

print(f"✅ CSV saved: {csv_path}")

conn.close()

print()
print("=" * 120)
print("EDGE ANALYSIS COMPLETE")
print("=" * 120)
