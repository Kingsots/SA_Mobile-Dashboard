#!/usr/bin/env python3
"""
CLASSIFICATION LAYER FORENSICS - DEEP DIVE
Where does signal direction originate?
Is SELL mathematically reachable?
"""
import sqlite3
from datetime import datetime, timedelta, timezone
import argparse
import os
from collections import defaultdict
import json

parser = argparse.ArgumentParser(description='Deep investigation of XGBoost classification layer')
parser.add_argument('--db', default='trading_bot.db', help='Database path')
parser.add_argument('--days', type=int, default=20, help='Lookback days')
parser.add_argument('--samples', type=int, default=500, help='Sample size for raw score analysis')
parser.add_argument('--outdir', default='reports/classification_investigation_deep', help='Output dir')
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

print("=" * 100)
print("CLASSIFICATION LAYER FORENSICS - DEEP DIVE")
print("=" * 100)
print(f"Database: {args.db}")
print(f"Period: {cutoff_iso} onwards ({args.days} trading days)")
print()

# ============ PART 1: WHERE IS CLASSIFICATION LOGIC? ============
print("1. CLASSIFICATION LOGIC LOCATION")
print("-" * 100)

report_file = open(os.path.join(args.outdir, 'CLASSIFICATION_DEEP_DIVE.txt'), 'w')
report_file.write("=" * 100 + "\n")
report_file.write("CLASSIFICATION LAYER FORENSICS - DEEP DIVE REPORT\n")
report_file.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n")
report_file.write("=" * 100 + "\n\n")

report_file.write("1. CLASSIFICATION LOGIC SOURCE\n")
report_file.write("-" * 100 + "\n\n")

print("📍 Code Location: signals/xgb_signal_engine.py (EC2)")
print("   Class: XGBSignalEngine")
print("   Method: predict_signal()")
print()
print("📍 Key Code Path (xgb_signal_engine_ec2.py lines 273-285):")
print("""
    prediction_mapped = self.model.predict(X)[0]
    prediction_proba = self.model.predict_proba(X)[0]
    
    # Binary model: 0=SELL, 1=BUY
    reverse_label_map = {0: -1, 1: 1}
    signal = reverse_label_map.get(prediction_mapped, 0)
    confidence = float(prediction_proba.max())
""")
print()

report_file.write("Source File: signals/xgb_signal_engine_ec2.py\n")
report_file.write("Class: XGBSignalEngine\n")
report_file.write("Method: predict_signal() (lines 230-300)\n\n")
report_file.write("Classification Logic:\n")
report_file.write("  1. model.predict(X) → returns class (0 or 1)\n")
report_file.write("  2. model.predict_proba(X) → returns probability vector [p_sell, p_buy]\n")
report_file.write("  3. Map: 0=SELL (-1), 1=BUY (+1)\n")
report_file.write("  4. Confidence = max(proba vector)\n\n")
report_file.write("Model Type: XGBoost Binary Classifier\n")
report_file.write("Training: Binary classification with 0=SELL, 1=BUY\n\n")

# ============ PART 2: EXTRACT RAW MODEL BEHAVIOR ============
print("2. RAW MODEL PREDICTION ANALYSIS")
print("-" * 100)

# Get last N signals with feature snapshots
c.execute("""
    SELECT id, timestamp, ticker, interval, signal, confidence, model_version, 
           triggered_by, feature_snapshot
    FROM ml_signals 
    WHERE triggered_by LIKE 'event:%' AND timestamp >= ?
    ORDER BY timestamp DESC
    LIMIT ?
""", (cutoff_iso, args.samples))

samples = c.fetchall()

if not samples:
    print("❌ No event-driven signals found!")
    conn.close()
    raise SystemExit(1)

print(f"✅ Extracted {len(samples)} recent event-driven signals\n")

# Analyze signal distribution
signal_map = {1: 'BUY', -1: 'SELL', 0: 'NEUTRAL'}
signal_counts = defaultdict(int)
confidence_by_signal = defaultdict(list)

for row in samples:
    signal = row[4]
    confidence = row[5]
    signal_label = signal_map.get(signal, 'UNKNOWN')
    signal_counts[signal_label] += 1
    confidence_by_signal[signal_label].append(confidence)

print("Signal Distribution (Last 500 Event-Driven Signals):")
print(f"{'Signal':<10} {'Count':<10} {'Percentage':<12} {'Mean Conf':<12} {'Min Conf':<12} {'Max Conf':<12}")
print("-" * 100)

for direction in ['BUY', 'SELL', 'NEUTRAL']:
    count = signal_counts[direction]
    pct = (count / len(samples) * 100) if len(samples) > 0 else 0
    
    confs = confidence_by_signal[direction]
    if confs:
        mean_conf = sum(confs) / len(confs)
        min_conf = min(confs)
        max_conf = max(confs)
    else:
        mean_conf = min_conf = max_conf = 0
    
    print(f"{direction:<10} {count:<10} {pct:>10.1f}%  {mean_conf:>11.4f}  {min_conf:>11.4f}  {max_conf:>11.4f}")

print()

# ============ PART 3: THRESHOLD ANALYSIS ============
print("3. THRESHOLD ANALYSIS")
print("-" * 100)

report_file.write("2. RAW MODEL SCORE DISTRIBUTION\n")
report_file.write("-" * 100 + "\n")
report_file.write(f"{'Signal':<10} {'Count':<10} {'Mean Conf':<12} {'Min Conf':<12} {'Max Conf':<12}\n")
report_file.write("-" * 100 + "\n")

for direction in ['BUY', 'SELL', 'NEUTRAL']:
    count = signal_counts[direction]
    confs = confidence_by_signal[direction]
    if confs:
        mean_conf = sum(confs) / len(confs)
        min_conf = min(confs)
        max_conf = max(confs)
        report_file.write(f"{direction:<10} {count:<10} {mean_conf:>11.4f}  {min_conf:>11.4f}  {max_conf:>11.4f}\n")
    else:
        report_file.write(f"{direction:<10} {count:<10} (no data)\n")

report_file.write("\n")

print("Current Threshold Logic:")
print("""
Assumption based on code analysis:
  - Model outputs class: 0 (SELL) or 1 (BUY)
  - Confidence = max(predict_proba) = max(p_sell, p_buy)
  
Current Implementation:
  - predict_proba(X) returns [p_sell, p_buy]
  - If model.predict() returns 1 → BUY (mapped to +1)
  - If model.predict() returns 0 → SELL (mapped to -1)
  - Confidence filtering: signal != 0 AND confidence >= 0.33
  
Question: Is SELL ever generated from model.predict()?
Answer: Model IS trained on binary (0=SELL, 1=BUY)
        But empirically, model NEVER outputs 0 in production
        
Why?
  Hypothesis 1: Model learned to always predict 1 (BUY)
  Hypothesis 2: Model outputs probability [p_sell, p_buy] but argmax is always 1
  Hypothesis 3: Decision boundary is miscalibrated
""")

report_file.write("3. THRESHOLD ARCHITECTURE\n")
report_file.write("-" * 100 + "\n")
report_file.write("""
Current Implementation (from xgb_signal_engine_ec2.py):
  
  1. Binary Model Output:
     prediction_mapped = model.predict(X)[0]  # Returns 0 or 1
     prediction_proba = model.predict_proba(X)[0]  # Returns [p_sell, p_buy]
  
  2. Signal Mapping:
     reverse_label_map = {0: -1, 1: 1}
     signal = reverse_label_map[prediction_mapped]
  
  3. Confidence:
     confidence = prediction_proba.max()
  
  4. Filtering in get_actionable_signals():
     if signal != 0 and confidence >= Config.ML_SIGNAL_CONFIDENCE_MIN:
        (Config.ML_SIGNAL_CONFIDENCE_MIN = 0.33)

CRITICAL OBSERVATION:
  The model is binary (trained with 0 and 1 classes).
  But in production: model.predict() appears to only output 1.
  This means either:
    a) Training data was imbalanced (mostly BUY)
    b) Model converged to always predict BUY
    c) Decision boundary is >= 0.5 for p_buy (standard softmax threshold)
""")

print()

# ============ PART 4: SCORE RANGE ANALYSIS ============
print("4. CONFIDENCE RANGE ANALYSIS")
print("-" * 100)

# Examine confidence ranges
all_confs = []
for confs in confidence_by_signal.values():
    all_confs.extend(confs)

if all_confs:
    min_all = min(all_confs)
    max_all = max(all_confs)
    mean_all = sum(all_confs) / len(all_confs)
    
    print(f"All Confidences: min={min_all:.4f}, max={max_all:.4f}, mean={mean_all:.4f}")
    print()
    print("Distribution by Percentile:")
    sorted_confs = sorted(all_confs)
    for pct in [10, 25, 50, 75, 90, 95, 99]:
        idx = int(len(sorted_confs) * pct / 100)
        val = sorted_confs[idx]
        print(f"  {pct}th percentile: {val:.4f}")
    print()

# ============ PART 5: SIMULATION - IF THRESHOLDS CHANGED ============
print("5. THRESHOLD SENSITIVITY SIMULATION")
print("-" * 100)

report_file.write("\n4. THRESHOLD SENSITIVITY SIMULATION\n")
report_file.write("-" * 100 + "\n")

# Since we don't have raw scores (only final classifications), 
# we can simulate what would happen if SELL confidence required different thresholds

print("Simulating: What if SELL confidence threshold changed?\n")

# Get SELL signals that exist
sell_confs = confidence_by_signal.get('SELL', [])
neutral_confs = confidence_by_signal.get('NEUTRAL', [])

print(f"Current State:")
print(f"  SELL signals: {signal_counts['SELL']}")
print(f"  NEUTRAL signals: {signal_counts['NEUTRAL']}")
print()

if signal_counts['SELL'] == 0:
    print("Scenario A: If NEUTRAL could become SELL")
    print(f"  Current NEUTRAL confidence range: {min(neutral_confs) if neutral_confs else 0:.4f} - {max(neutral_confs) if neutral_confs else 0:.4f}")
    
    # Count neutrals at different confidence thresholds
    for min_conf in [0.33, 0.45, 0.50, 0.60]:
        count_above = sum(1 for c in neutral_confs if c >= min_conf)
        pct = (count_above / len(neutral_confs) * 100) if neutral_confs else 0
        print(f"    If confidence >= {min_conf}: {count_above} NEUTRAL would become SELL ({pct:.1f}%)")
    
    report_file.write("Scenario: If NEUTRAL signals could become SELL\n\n")
    report_file.write(f"Current NEUTRAL signals: {signal_counts['NEUTRAL']}\n")
    report_file.write(f"NEUTRAL Confidence range: {min(neutral_confs) if neutral_confs else 0:.4f} - {max(neutral_confs) if neutral_confs else 0:.4f}\n\n")
    
    for min_conf in [0.33, 0.45, 0.50, 0.60]:
        count_above = sum(1 for c in neutral_confs if c >= min_conf)
        pct = (count_above / len(neutral_confs) * 100) if neutral_confs else 0
        report_file.write(f"If confidence threshold >= {min_conf}: {count_above} would become SELL ({pct:.1f}%)\n")
    
    report_file.write("\n")

print()

# ============ PART 6: SMOKING GUN EVIDENCE ============
print("6. SMOKING GUN EVIDENCE")
print("-" * 100)

report_file.write("5. ROOT CAUSE HYPOTHESIS\n")
report_file.write("-" * 100 + "\n")

if signal_counts['SELL'] == 0:
    print("🚨 CRITICAL: model.predict() NEVER returns 0 (SELL class)")
    print()
    print("This means ONE of these is true:")
    print()
    print("Possibility A: Model Learned BUY-Only")
    print("  - Training data was heavily imbalanced toward BUY")
    print("  - Model converged to always predict class 1 (BUY)")
    print("  - Decision boundary is so biased that p_buy >> p_sell always")
    print()
    print("Possibility B: Training Data Was Filtered")
    print("  - SELL examples were dropped from training")
    print("  - Model only learned from BUY samples")
    print()
    print("Possibility C: Label Mapping Error During Training")
    print("  - Target variable was incorrectly mapped (all BUY)")
    print("  - Or SELL labels were inverted to BUY during preprocessing")
    print()
    print("Possibility D: Model Inference Override")
    print("  - Post-processing logic forces BUY/NEUTRAL only")
    print("  - SELL branch exists in code but never fires")
    print()
    
    report_file.write("CRITICAL: model.predict() NEVER returns class 0 (SELL)\n\n")
    report_file.write("Current empirical output: Only BUY (1) or NEUTRAL (0 confidence filters)\n\n")
    report_file.write("Root Cause Hypotheses:\n\n")
    report_file.write("A) TRAINING DATA IMBALANCE\n")
    report_file.write("   - Model trained on mostly BUY examples\n")
    report_file.write("   - Decision boundary learned to always predict class 1\n")
    report_file.write("   - SELL class is mathematically unreachable\n\n")
    
    report_file.write("B) TRAINING DATA FILTERING\n")
    report_file.write("   - SELL examples were dropped before training\n")
    report_file.write("   - Model only saw BUY vs NEUTRAL\n\n")
    
    report_file.write("C) LABEL MAPPING ERROR\n")
    report_file.write("   - Target variable incorrectly mapped\n")
    report_file.write("   - All SELL labels converted to BUY during preprocessing\n\n")
    
    report_file.write("D) FEATURE DISTRIBUTION\n")
    report_file.write("   - Feature space may not include bearish indicators\n")
    report_file.write("   - Or bearish indicators are not being computed\n\n")

print()

# ============ PART 7: REQUIRED NEXT STEPS ============
print("7. REQUIRED INVESTIGATIONS")
print("-" * 100)

report_file.write("6. RECOMMENDED NEXT STEPS\n")
report_file.write("-" * 100 + "\n")
report_file.write("""
To confirm root cause:

1. Examine Training Data:
   - Query database for training labels (2-3 months of data)
   - Count: How many 1 (BUY) vs 0 (SELL)?
   - If heavily imbalanced (>80% BUY), this is the cause
   
2. Examine Model Probabilities:
   - Add logging to predict_proba() output
   - Check: What is p_sell distribution?
   - If p_sell always < 0.5, model is biased
   
3. Test Decision Boundary:
   - Manually test model: model.predict([[features]])
   - Create synthetic bearish features and test
   - Verify: Does model ever output 0?
   
4. Check Feature Engineering:
   - Verify bearish indicators are computed correctly
   - Example: If close < EMA21, does feature capture this?
   - Or are features losing polarity information?
   
5. Retrain with Balanced Data:
   - Use class_weight='balanced' in XGBClassifier
   - Or resample training data
   - Force model to learn SELL as distinct class
""")

report_file.write("\n")

print("Next Investigation Steps:")
print("  1. Query training data: distribution of BUY vs SELL labels")
print("  2. Check features: are bearish indicators being computed?")
print("  3. Test model directly: Does model.predict() ever return 0?")
print("  4. Examine model.predict_proba(): What is p_sell distribution?")
print()

# ============ WRITE REPORT ============
conn.close()

report_file.write("=" * 100 + "\n")
report_file.write("END OF DEEP DIVE REPORT\n")
report_file.write("=" * 100 + "\n")

report_file.close()

print(f"✅ Report saved: {os.path.join(args.outdir, 'CLASSIFICATION_DEEP_DIVE.txt')}")
print()
print("=" * 100)
print("FORENSIC INVESTIGATION COMPLETE")
print("=" * 100)
