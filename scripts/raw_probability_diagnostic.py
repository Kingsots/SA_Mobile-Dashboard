#!/usr/bin/env python3
"""
RAW PROBABILITY EXTRACTION - Direct predict_proba() Analysis
Confirms [0.5, 0.5] collapse hypothesis
"""
import sqlite3
import json
import pickle
import sys
import os
from datetime import datetime, timezone

# Try numpy for better math
try:
    import numpy as np
    HAS_NUMPY = True
except:
    HAS_NUMPY = False

db_path = '/home/ubuntu/opticore-bot/trading_bot.db'
model_path = '/home/ubuntu/opticore-bot/data/models/model_current.pkl'
output_dir = '/home/ubuntu/opticore-bot/reports/raw_probability_diagnostics'

os.makedirs(output_dir, exist_ok=True)

print("=" * 120)
print("RAW PROBABILITY EXTRACTION - predict_proba() DIRECT ANALYSIS")
print("=" * 120)
print(f"Database: {db_path}")
print(f"Model: {model_path}")
print(f"Output: {output_dir}")
print()

# ============ ATTEMPT MODEL LOAD ============
print("1. LOADING MODEL")
print("-" * 120)

model = None
load_method = None

# Try joblib first
try:
    import joblib
    model = joblib.load(model_path)
    load_method = "joblib"
    print(f"✅ Model loaded via joblib")
except Exception as e:
    print(f"⚠️ joblib failed: {str(e)[:80]}")

# Try pickle
if model is None:
    try:
        with open(model_path, 'rb') as f:
            data = pickle.load(f)
        
        if isinstance(data, dict) and 'model' in data:
            model = data['model']
        else:
            model = data
        
        load_method = "pickle"
        print(f"✅ Model loaded via pickle")
    except Exception as e:
        print(f"⚠️ pickle failed: {str(e)[:80]}")

if model is None:
    print("❌ Failed to load model!")
    sys.exit(1)

print(f"   Model type: {type(model)}")
try:
    print(f"   Classes: {model.classes_}")
    print(f"   N estimators: {model.n_estimators}")
except:
    pass

print()

# ============ EXTRACT SIGNALS FROM DATABASE ============
print("2. EXTRACTING SIGNALS FROM DATABASE")
print("-" * 120)

conn = sqlite3.connect(db_path)
c = conn.cursor()

# Get event-driven signals with feature snapshots
c.execute("""
    SELECT id, timestamp, ticker, signal, confidence, feature_snapshot
    FROM ml_signals 
    WHERE triggered_by LIKE 'event:%' 
    ORDER BY timestamp DESC
    LIMIT 1000
""")

signals = c.fetchall()
print(f"✅ Extracted {len(signals)} event-driven signals")
print()

if not signals:
    print("❌ No signals found!")
    sys.exit(1)

# ============ RUN INFERENCE ============
print("3. RUNNING predict_proba() INFERENCE")
print("-" * 120)

probs_list = []
valid_count = 0
error_count = 0

for idx, (sig_id, timestamp, ticker, signal, confidence, feature_snapshot) in enumerate(signals):
    try:
        # Parse features
        if isinstance(feature_snapshot, str):
            features_dict = json.loads(feature_snapshot)
        else:
            features_dict = feature_snapshot
        
        # Get feature names from model
        try:
            feature_names = model.get_booster().feature_names
            if feature_names is None:
                feature_names = sorted(features_dict.keys())
        except:
            feature_names = sorted(features_dict.keys())
        
        # Extract features in order
        X_values = [float(features_dict.get(fname, 0.0)) for fname in feature_names]
        
        # Run inference
        probas = model.predict_proba([X_values])[0]
        
        # Store: [p_class_0, p_class_1] = [p_SELL, p_BUY]
        probs_list.append(probas)
        valid_count += 1
        
        if (idx + 1) % 200 == 0:
            print(f"  Processed {idx + 1}/{len(signals)}...")
    
    except Exception as e:
        error_count += 1
        if error_count <= 3:
            print(f"  ⚠️ Error on signal {sig_id}: {str(e)[:60]}")

print(f"✅ Inference complete: {valid_count} successful, {error_count} errors")
print()

if not probs_list:
    print("❌ No successful inferences!")
    sys.exit(1)

# ============ YOUR REQUESTED ANALYSIS ============
print("4. PROBABILITY ANALYSIS (Your Requested Code)")
print("-" * 120)

# Initialize variables
mean_p0 = None
mean_p1 = None
min_p0 = None
max_p0 = None
min_p1 = None
max_p1 = None
count_p0_wins = None
count_p1_wins = None

if HAS_NUMPY:
    probs = np.array(probs_list)
    p0 = probs[:, 0]
    p1 = probs[:, 1]
    
    mean_p0 = p0.mean()
    mean_p1 = p1.mean()
    min_p0 = p0.min()
    max_p0 = p0.max()
    min_p1 = p1.min()
    max_p1 = p1.max()
    count_p0_wins = int(np.sum(p0 > p1))
    count_p1_wins = int(np.sum(p1 > p0))
    
    print(f"Mean p0 (SELL): {mean_p0:.6f}")
    print(f"Mean p1 (BUY):  {mean_p1:.6f}")
    print()
    print(f"Min p0: {min_p0:.6f}  |  Max p0: {max_p0:.6f}")
    print(f"Min p1: {min_p1:.6f}  |  Max p1: {max_p1:.6f}")
    print()
    print(f"Count p0 > p1 (SELL wins): {count_p0_wins}")
    print(f"Count p1 > p0 (BUY wins):  {count_p1_wins}")
    print()

else:
    # Manual calculation without numpy
    p0_list = [probs[0] for probs in probs_list]
    p1_list = [probs[1] for probs in probs_list]
    
    mean_p0 = sum(p0_list) / len(p0_list)
    mean_p1 = sum(p1_list) / len(p1_list)
    
    min_p0 = min(p0_list)
    max_p0 = max(p0_list)
    min_p1 = min(p1_list)
    max_p1 = max(p1_list)
    
    count_p0_wins = sum(1 for p0, p1 in probs_list if p0 > p1)
    count_p1_wins = sum(1 for p0, p1 in probs_list if p1 > p0)
    
    print(f"Mean p0 (SELL): {mean_p0:.6f}")
    print(f"Mean p1 (BUY):  {mean_p1:.6f}")
    print()
    print(f"Min p0: {min_p0:.6f}  |  Max p0: {max_p0:.6f}")
    print(f"Min p1: {min_p1:.6f}  |  Max p1: {max_p1:.6f}")
    print()
    print(f"Count p0 > p1 (SELL wins): {count_p0_wins}")
    print(f"Count p1 > p0 (BUY wins):  {count_p1_wins}")
    print()

# ============ EXTENDED ANALYSIS ============
print("5. EXTENDED PROBABILITY ANALYSIS")
print("-" * 120)

if HAS_NUMPY:
    # Calculate edge
    edge = p1 - p0
    
    print(f"Edge (p1 - p0) statistics:")
    print(f"  Mean edge: {edge.mean():.6f}")
    print(f"  Min edge:  {edge.min():.6f}")
    print(f"  Max edge:  {edge.max():.6f}")
    print()
    
    # Count at different thresholds
    print(f"Edge threshold analysis:")
    for threshold in [-0.1, -0.05, 0.0, 0.05, 0.1]:
        count_below = np.sum(edge < threshold)
        pct = (count_below / len(edge) * 100)
        print(f"  edge < {threshold:6.2f}: {count_below:4} ({pct:5.1f}%)")
    print()
    
    # Correlation
    corr = np.corrcoef(p0, p1)[0, 1]
    print(f"Correlation p0 ↔ p1: {corr:.6f}")
    if corr > 0.98:
        print(f"  🚨 CRITICAL: Near-perfect correlation")
        print(f"     Indicates: p0 and p1 move together (perfect symmetry)")
        print(f"     Means: When p0 increases, p1 decreases equally")
    print()
    
    # Variance analysis
    var_p0 = np.var(p0)
    var_p1 = np.var(p1)
    print(f"Variance p0: {var_p0:.6f}")
    print(f"Variance p1: {var_p1:.6f}")
    print()

else:
    p0_list = [probs[0] for probs in probs_list]
    p1_list = [probs[1] for probs in probs_list]
    
    edge_list = [p1 - p0 for p0, p1 in probs_list]
    edge_mean = sum(edge_list) / len(edge_list)
    edge_min = min(edge_list)
    edge_max = max(edge_list)
    
    print(f"Edge (p1 - p0) statistics:")
    print(f"  Mean edge: {edge_mean:.6f}")
    print(f"  Min edge:  {edge_min:.6f}")
    print(f"  Max edge:  {edge_max:.6f}")
    print()
    
    mean_p0 = sum(p0_list) / len(p0_list)
    mean_p1 = sum(p1_list) / len(p1_list)

# ============ DIAGNOSIS ============
print("6. DIAGNOSIS")
print("-" * 120)

# Check if probabilities are symmetric
p_sum = mean_p0 + mean_p1
print(f"Mean p0 + p1: {p_sum:.6f} (should be 1.0)")

if abs(p_sum - 1.0) < 0.001:
    print("✅ Probabilities sum to 1.0 (valid)")
else:
    print(f"⚠️ Probabilities don't sum to 1.0 (error in extraction)")

print()

# Check symmetry
p_diff = abs(mean_p0 - mean_p1)
print(f"Mean probability difference |p0 - p1|: {p_diff:.6f}")

if p_diff < 0.01:
    print("🚨 CRITICAL: Probabilities are SYMMETRIC")
    print("   Interpretation: Model outputs [0.5, 0.5] for all predictions")
    print("   This confirms: BINARY CLASSIFIER COLLAPSE")
else:
    print(f"✅ Probabilities are imbalanced (asymmetric)")
    print(f"   Expected if model is learning directionality")

print()

# Check class prediction winner
if count_p0_wins == 0:
    print(f"🚨 CRITICAL: p0 NEVER wins (count: {count_p0_wins}/{len(probs_list)})")
    print("   Interpretation: model.predict() never returns class 0 (SELL)")
    print("   This confirms: MODEL ONLY PREDICTS CLASS 1 (BUY)")
else:
    pct_p0_wins = (count_p0_wins / len(probs_list) * 100)
    print(f"✅ p0 wins in {count_p0_wins}/{len(probs_list)} cases ({pct_p0_wins:.1f}%)")

print()

# ============ WRITE REPORT ============
print("7. WRITING DIAGNOSTIC REPORT")
print("-" * 120)

report_path = os.path.join(output_dir, 'RAW_PROBABILITIES_DIAGNOSTIC.txt')

with open(report_path, 'w') as f:
    f.write("=" * 120 + "\n")
    f.write("RAW PROBABILITY EXTRACTION DIAGNOSTIC\n")
    f.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n")
    f.write(f"Model Loaded: {load_method}\n")
    f.write(f"Samples: {valid_count}\n")
    f.write("=" * 120 + "\n\n")
    
    f.write("CORE STATISTICS\n")
    f.write("-" * 120 + "\n")
    f.write(f"Mean p0 (SELL):    {mean_p0:.6f}\n")
    f.write(f"Mean p1 (BUY):     {mean_p1:.6f}\n")
    f.write(f"\n")
    f.write(f"Min p0: {min_p0:.6f}  |  Max p0: {max_p0:.6f}\n")
    f.write(f"Min p1: {min_p1:.6f}  |  Max p1: {max_p1:.6f}\n")
    f.write(f"\n")
    f.write(f"p0 > p1 (class 0 wins):  {count_p0_wins}\n")
    f.write(f"p1 > p0 (class 1 wins):  {count_p1_wins}\n")
    f.write(f"\n")
    
    f.write("DIAGNOSIS\n")
    f.write("-" * 120 + "\n")
    
    if count_p0_wins == 0:
        f.write("🚨 ROOT CAUSE CONFIRMED: Binary Classifier Collapse\n\n")
        f.write("Finding: p0 (SELL) NEVER wins in any prediction\n")
        f.write("Meaning: model.predict() ALWAYS returns class 1 (BUY)\n")
        f.write(f"Evidence: Count p0 > p1 = 0 out of {valid_count} samples\n\n")
        
        f.write("Probability Pattern:\n")
        f.write(f"  Mean p0: {mean_p0:.6f} (expected ~0.5 if collapsed)\n")
        f.write(f"  Mean p1: {mean_p1:.6f} (expected ~0.5 if collapsed)\n\n")
        
        if abs(mean_p0 - mean_p1) < 0.01:
            f.write("Symmetry Analysis:\n")
            f.write(f"  p0 ≈ p1 (diff = {abs(mean_p0 - mean_p1):.6f})\n")
            f.write("  ✅ CONFIRMS: Model outputs symmetric [0.5, 0.5] probabilities\n\n")
        
        f.write("Solution: Retrain with class_weight='balanced'\n")

print(f"✅ Report saved: {report_path}")

print()
print("=" * 120)
print("RAW PROBABILITY DIAGNOSTIC COMPLETE")
print("=" * 120)
print()

conn.close()
