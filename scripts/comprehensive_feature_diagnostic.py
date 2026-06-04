#!/usr/bin/env python3
"""
COMPREHENSIVE DIAGNOSTIC: Feature mismatch investigation
Check if model expects lag1 features but snapshot only has raw features
"""
import sqlite3
import json
import sys

db_path = '/home/ubuntu/opticore-bot/trading_bot.db'
model_path = '/home/ubuntu/opticore-bot/data/models/model_current.pkl'

print("=" * 120)
print("COMPREHENSIVE FEATURE DIAGNOSTIC")
print("=" * 120)
print()

# 1. Try loading model
print("1. Loading model...")
try:
    import joblib
    model = joblib.load(model_path)
    print("   ✅ Model loaded\n")
except Exception as e:
    print(f"   ❌ Failed: {e}\n")
    sys.exit(1)

# 2. Get model's expected features
print("2. Model's expected features:")
try:
    booster = model.get_booster()
    feature_names = booster.feature_names
    print(f"   Feature names from model: {feature_names}")
    print(f"   Count: {len(feature_names) if feature_names else 'None'}\n")
except Exception as e:
    feature_names = None
    print(f"   ⚠️  Could not get feature names: {e}\n")

# 3. Check a sample signal
print("3. Checking a sample event-driven signal:")
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("""
    SELECT id, timestamp, ticker, interval, signal, feature_snapshot
    FROM ml_signals 
    WHERE triggered_by LIKE 'event:%' 
    ORDER BY timestamp DESC
    LIMIT 1
""")

result = c.fetchone()
if not result:
    print("   ❌ No event-driven signals found\n")
    sys.exit(1)

sig_id, timestamp, ticker, interval, db_signal, feature_snapshot = result
print(f"   Signal ID: {sig_id}")
print(f"   Timestamp: {timestamp}")
print(f"   Ticker: {ticker} {interval}")
print(f"   DB signal: {db_signal}\n")

# 4. Parse the snapshot
print("4. Parsing feature snapshot:")
try:
    if isinstance(feature_snapshot, str):
        features_dict = json.loads(feature_snapshot)
    else:
        features_dict = feature_snapshot
    print(f"   Feature count in snapshot: {len(features_dict)}")
    print(f"   Features in snapshot: {list(features_dict.keys())}\n")
except Exception as e:
    print(f"   ❌ Error parsing snapshot: {e}\n")
    sys.exit(1)

# 5. Check for lag1 features
print("5. Checking for lag1 features:")
lag1_features = [f for f in features_dict.keys() if 'lag1' in f]
print(f"   Lag1 features in snapshot: {lag1_features if lag1_features else 'NONE'}")
print(f"   Count: {len(lag1_features)}\n")

if not lag1_features:
    print("   ⚠️  ALERT: Snapshot has NO lag1 features!")
    print("   But model may have been trained on lag1 features!")
    print()

# 6. Try calling predict_proba with snapshot features
print("6. Calling model.predict_proba() with snapshot features:")
try:
    # Extract features in the same order the model expects
    if feature_names is not None:
        X_values = [[float(features_dict.get(fname, 0.0)) for fname in feature_names]]
        print(f"   Using {len(feature_names)} features from model.feature_names")
    else:
        # Fallback: use all features in snapshot
        feature_names_list = sorted(features_dict.keys())
        X_values = [[float(features_dict.get(fname, 0.0)) for fname in feature_names_list]]
        print(f"   Using {len(feature_names_list)} features from snapshot (sorted)")
    
    proba = model.predict_proba(X_values)[0]
    prediction = model.predict(X_values)[0]
    
    print(f"   ✅ Prediction successful!")
    print(f"   p_sell (class 0): {proba[0]:.6f}")
    print(f"   p_buy (class 1):  {proba[1]:.6f}")
    print(f"   Predicted class: {prediction}")
    print(f"   Edge (p_buy - p_sell): {(proba[1] - proba[0]):.6f}")
    print()
    
    # Map class to signal
    signal_map = {0: -1, 1: 1}
    predicted_signal = signal_map.get(prediction, 0)
    signal_names = {0: 'NEUTRAL', 1: 'BUY', -1: 'SELL'}
    
    print(f"   Predicted signal (mapped): {signal_names[predicted_signal]} ({predicted_signal})")
    print(f"   DB signal: {signal_names[db_signal]} ({db_signal})")
    
    if predicted_signal != db_signal:
        print(f"   ❌ MISMATCH: Predicted SELL={predicted_signal==-1}, DB SELL={db_signal==-1}")
    else:
        print(f"   ✅ MATCH: Predictions align with database")
    print()
    
except Exception as e:
    print(f"   ❌ Error calling predict: {e}\n")
    import traceback
    traceback.print_exc()

# 7. Summary
print()
print("=" * 120)
print("SUMMARY:")
print("=" * 120)
if not lag1_features:
    print()
    print("🚨 ISSUE IDENTIFIED:")
    print("   - Snapshot features: Raw OHLC/indicators only")
    print("   - Model likely trained on: Lag1 indicators")
    print("   - Current behavior: Predict_proba gets raw features")
    print()
    print("   IMPACT:")
    print("   - If model.predict() ignores lag1 features, predictions may be wrong")
    print("   - If bypass script substitutes 0.0 for lag1, predictions are definitely wrong")
    print("   - Signals may default to NEUTRAL due to NaN lag1 in generate_signal")
    print()
    print("   SOLUTION:")
    print("   - Store lag1 features alongside raw features in snapshot")
    print("   - OR: Use OHLC to compute lag indicators on-the-fly during inference")
    print("   - OR: Retrain model on raw features instead of lag1")
else:
    print()
    print("✅ Snapshot includes lag1 features")
    print("   Model predictions should be accurate")

conn.close()
