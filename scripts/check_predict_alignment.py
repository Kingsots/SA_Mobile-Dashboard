#!/usr/bin/env python3
"""
Check model.predict() vs predict_proba() mismatch
Verify if predict() returns correct classes for 56.2% SELL probability cases
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
except:
    print("Failed to load model")
    sys.exit(1)

conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("""
    SELECT id, signal, confidence, feature_snapshot
    FROM ml_signals 
    WHERE triggered_by LIKE 'event:%' 
    ORDER BY timestamp DESC
    LIMIT 100
""")

signals = c.fetchall()

print("=" * 120)
print("CHECKING: model.predict() vs predict_proba() alignment")
print("=" * 120)
print()

mismatches = 0
matches = 0

signal_map = {0: -1, 1: 1}  # XGBoost class → signal mapping
reverse_map = {-1: 0, 1: 1}  # signal → XGBoost class

for sig_id, db_signal, db_confidence, feature_snapshot in signals:
    try:
        if isinstance(feature_snapshot, str):
            features_dict = json.loads(feature_snapshot)
        else:
            features_dict = feature_snapshot
        
        feature_names = sorted(features_dict.keys())
        X_values = [[float(features_dict.get(fname, 0.0)) for fname in feature_names]]
        
        # Get both predict and predict_proba
        predicted_class = model.predict(X_values)[0]
        probas = model.predict_proba(X_values)[0]
        
        # Map class to signal
        predicted_signal = signal_map[predicted_class]
        
        # Check which class has higher probability
        p_sell = probas[0]
        p_buy = probas[1]
        
        db_signal_name = {0: 'NEUTRAL', 1: 'BUY', -1: 'SELL'}.get(db_signal, 'UNKNOWN')
        predicted_signal_name = {0: 'NEUTRAL', 1: 'BUY', -1: 'SELL'}.get(predicted_signal, 'UNKNOWN')
        winner = "p_sell" if p_sell > p_buy else "p_buy"
        
        if predicted_signal != db_signal:
            mismatches += 1
            print(f"MISMATCH #{mismatches}:")
            print(f"  DB signal: {db_signal_name} ({db_signal})")
            print(f"  Predicted signal: {predicted_signal_name} ({predicted_signal})")
            print(f"  Probabilities: p_sell={p_sell:.4f}, p_buy={p_buy:.4f}")
            print(f"  Winner: {winner} (class {predicted_class})")
            print(f"  DB confidence: {db_confidence:.4f}")
            print()
        else:
            matches += 1
    
    except Exception as e:
        print(f"Error on signal {sig_id}: {str(e)[:60]}")

print()
print("=" * 120)
print(f"SUMMARY: {matches} matches, {mismatches} MISMATCHES")
print("=" * 120)

if mismatches > 0:
    print()
    print("🚨 CRITICAL: model.predict() is NOT matching predict_proba() winner!")
    print("This suggests:")
    print("  1. Model was trained with different label encoding")
    print("  2. model.predict() is not reliably picking the argmax of predict_proba()")
    print("  3. There's a bug in how predictions are being mapped")

conn.close()
