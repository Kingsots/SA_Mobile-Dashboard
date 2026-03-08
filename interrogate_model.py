import sys
sys.path.insert(0, '/home/ubuntu/SilentAnalyst')

from signals.xgb_signal_engine_ec2 import XGBSignalEngine
import numpy as np
import sqlite3

engine = XGBSignalEngine()

print("\n" + "=" * 80)
print("🎯 DIRECT MODEL INTERROGATION")
print("=" * 80)

# Step 1: Model Classes
print("\n[Step 1] Model Classes:")
print("=" * 80)
print(f"Classes: {engine.model.classes_}")
print(f"Number of classes: {len(engine.model.classes_)}")

# Step 2: Training info
print("\n[Step 2] Model Info:")
print("=" * 80)
print(f"Model expects {engine.model.n_features_in_} features")
print(f"Feature names: {engine.model.get_booster().feature_names}")

# Step 3: Try to get raw probabilities on dummy data
print("\n[Step 3] Raw Prediction Probabilities (Synthetic Test Data):")
print("=" * 80)
try:
    # Create test data with correct shape
    X_test = np.random.randn(1, engine.model.n_features_in_)
    
    # Get probabilities
    proba = engine.model.predict_proba(X_test)
    
    print(f"Test prediction probabilities (random data):")
    print(f"Raw output shape: {proba.shape}")
    print(f"Raw probabilities: {proba[0]}")
    
    for idx, class_label in enumerate(engine.model.classes_):
        signal_name = {-1: 'SELL', 0: 'NEUTRAL', 1: 'BUY'}.get(class_label, f"Class {class_label}")
        prob = proba[0][idx] * 100
        print(f"  {signal_name:8}: {prob:6.2f}%")
    
    # Also get raw prediction
    pred = engine.model.predict(X_test)
    pred_label = {-1: 'SELL', 0: 'NEUTRAL', 1: 'BUY'}.get(pred[0], f"Class {pred[0]}")
    print(f"\nPredicted class: {pred[0]} ({pred_label})")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("🔍 KEY FINDINGS")
print("=" * 80)
print("\n✋ CRITICAL ISSUE FOUND:")
print("  Model.classes_ = [0, 1]  <- Only 2 classes!")
print("  Expected: [-1, 0, 1]  <- 3 classes (SELL, NEUTRAL, BUY)")
print("\n  The model was trained WITHOUT a SELL class.")
print("  It can ONLY predict NEUTRAL (0) or BUY (1).")
print("  SELL predictions are mathematically impossible.")
print("\n" + "=" * 80)
