import sys
sys.path.insert(0, '/home/ubuntu/SilentAnalyst')

from signals.xgb_signal_engine_ec2 import XGBSignalEngine
import numpy as np

engine = XGBSignalEngine()

print("\n" + "=" * 80)
print("MODEL FEATURE REQUIREMENTS")
print("=" * 80)
print(f"Model expects {engine.model.n_features_in_} features")
print(f"Model feature names (if available):")

# Try to get feature names from model
if hasattr(engine.model, 'get_booster'):
    booster = engine.model.get_booster()
    if hasattr(booster, 'feature_names'):
        print(f"Feature names: {booster.feature_names}")
    else:
        print("No feature names stored in model")
else:
    print("Cannot access booster")

# Check which features are actually used
try:
    print(f"\nFeature importance (normalized):")
    importance = engine.model.feature_importances_
    for i, imp in enumerate(importance):
        if imp > 0:
            print(f"  Feature {i}: {imp:.4f}")
except:
    pass

print("\n" + "=" * 80)
