#!/usr/bin/env python3
"""
Bypass ALL event processing - Call model directly
Get raw signal distribution using only predict_proba() output
"""
import sqlite3
import json
import sys
import os

db_path = '/home/ubuntu/opticore-bot/trading_bot.db'
model_path = '/home/ubuntu/opticore-bot/data/models/model_current.pkl'

try:
    import joblib
    model = joblib.load(model_path)
    print("✅ Model loaded via joblib")
except Exception as e:
    print(f"❌ Failed to load model: {e}")
    sys.exit(1)

try:
    import numpy as np
    HAS_NUMPY = True
except:
    HAS_NUMPY = False

conn = sqlite3.connect(db_path)
c = conn.cursor()

# Get 100 event-driven signals
c.execute("""
    SELECT id, signal, confidence, feature_snapshot
    FROM ml_signals 
    WHERE triggered_by LIKE 'event:%' 
    ORDER BY timestamp DESC
    LIMIT 100
""")

signals = c.fetchall()
print(f"✅ Extracted {len(signals)} event-driven signals\n")

print("=" * 120)
print("RAW SIGNAL DISTRIBUTION - Bypassing Event Processing")
print("=" * 120)
print()

# Thresholds
EDGE_BUY_THRESHOLD = 0.08
EDGE_SELL_THRESHOLD = -0.08

raw_signals = []
db_signals = []
mismatches = 0

for idx, (sig_id, db_signal, db_confidence, feature_snapshot) in enumerate(signals):
    try:
        # Parse features
        if isinstance(feature_snapshot, str):
            features_dict = json.loads(feature_snapshot)
        else:
            features_dict = feature_snapshot
        
        # Get feature names
        try:
            feature_names = model.get_booster().feature_names
            if feature_names is None:
                feature_names = sorted(features_dict.keys())
        except:
            feature_names = sorted(features_dict.keys())
        
        # Extract features
        X_values = [[float(features_dict.get(fname, 0.0)) for fname in feature_names]]
        
        # Get probabilities
        proba = model.predict_proba(X_values)[0]
        p_sell = proba[0]
        p_buy = proba[1]
        edge = p_buy - p_sell
        
        # Determine raw signal based on edge threshold
        if edge > EDGE_BUY_THRESHOLD:
            raw_signal = "BUY"
        elif edge < EDGE_SELL_THRESHOLD:
            raw_signal = "SELL"
        else:
            raw_signal = "NEUTRAL"
        
        raw_signals.append(raw_signal)
        
        # Database signal
        db_signal_map = {0: "NEUTRAL", 1: "BUY", -1: "SELL"}
        db_signal_name = db_signal_map.get(db_signal, "UNKNOWN")
        db_signals.append(db_signal_name)
        
        # Track mismatches
        if raw_signal != db_signal_name:
            mismatches += 1
    
    except Exception as e:
        print(f"Error on signal {sig_id}: {str(e)[:60]}")

print(f"1. RAW MODEL OUTPUT (Using edge thresholds: BUY > 0.08, SELL < -0.08)")
print("-" * 120)

if HAS_NUMPY:
    from collections import Counter
    raw_counts = Counter(raw_signals)
    db_counts = Counter(db_signals)
    
    print(f"\nRaw signals from model probabilities:")
    total = len(raw_signals)
    for signal in ["BUY", "SELL", "NEUTRAL"]:
        count = raw_counts.get(signal, 0)
        pct = (count / total * 100) if total > 0 else 0
        print(f"  {signal:<10}: {count:4} ({pct:5.1f}%)")
    
    print(f"\nDatabase stored signals:")
    for signal in ["BUY", "SELL", "NEUTRAL"]:
        count = db_counts.get(signal, 0)
        pct = (count / total * 100) if total > 0 else 0
        print(f"  {signal:<10}: {count:4} ({pct:5.1f}%)")
else:
    # Manual count
    from collections import Counter
    raw_counts = Counter(raw_signals)
    db_counts = Counter(db_signals)
    
    print(f"\nRaw signals from model probabilities:")
    total = len(raw_signals)
    for signal in ["BUY", "SELL", "NEUTRAL"]:
        count = raw_counts.get(signal, 0)
        pct = (count / total * 100) if total > 0 else 0
        print(f"  {signal:<10}: {count:4} ({pct:5.1f}%)")
    
    print(f"\nDatabase stored signals:")
    for signal in ["BUY", "SELL", "NEUTRAL"]:
        count = db_counts.get(signal, 0)
        pct = (count / total * 100) if total > 0 else 0
        print(f"  {signal:<10}: {count:4} ({pct:5.1f}%)")

print()
print("=" * 120)
print("2. COMPARISON")
print("=" * 120)

raw_buy = raw_counts.get("BUY", 0)
raw_sell = raw_counts.get("SELL", 0)
raw_neutral = raw_counts.get("NEUTRAL", 0)

db_buy = db_counts.get("BUY", 0)
db_sell = db_counts.get("SELL", 0)
db_neutral = db_counts.get("NEUTRAL", 0)

print()
print(f"{'Signal':<10} {'Raw Model':<20} {'Database':<20} {'Difference':<15}")
print("-" * 120)
print(f"{'BUY':<10} {raw_buy:4} ({raw_buy/total*100:5.1f}%)      {db_buy:4} ({db_buy/total*100:5.1f}%)      {raw_buy-db_buy:+5} ({(raw_buy-db_buy)/total*100:+5.1f}%)")
print(f"{'SELL':<10} {raw_sell:4} ({raw_sell/total*100:5.1f}%)      {db_sell:4} ({db_sell/total*100:5.1f}%)      {raw_sell-db_sell:+5} ({(raw_sell-db_sell)/total*100:+5.1f}%)")
print(f"{'NEUTRAL':<10} {raw_neutral:4} ({raw_neutral/total*100:5.1f}%)      {db_neutral:4} ({db_neutral/total*100:5.1f}%)      {raw_neutral-db_neutral:+5} ({(raw_neutral-db_neutral)/total*100:+5.1f}%)")

print()
print("=" * 120)
print("3. KEY FINDING")
print("=" * 120)

print()
if raw_sell > 0 and db_sell == 0:
    print(f"🚨 CRITICAL: Model generates {raw_sell} SELL signals ({raw_sell/total*100:.1f}%)")
    print(f"             but database has {db_sell} SELL signals (0.0%)")
    print(f"             GAP: {raw_sell} lost SELL signals")
    print(f"             LOST: {raw_sell/total*100:.1f}% of SELL potential")
    print()
    print("Conclusion: ALL model SELL signals are being SUPPRESSED or")
    print("            converted to NEUTRAL somewhere in event processing")
    
elif raw_sell > db_sell:
    print(f"⚠️  Model generates {raw_sell} SELL, database has {db_sell}")
    print(f"    MISSING: {raw_sell - db_sell} SELL signals")
    print(f"    They're being converted to: {raw_neutral - db_neutral} NEUTRAL")

else:
    print(f"✅ Model output matches database:")
    print(f"   Raw: {raw_sell} SELL, DB: {db_sell} SELL")

print()

conn.close()
