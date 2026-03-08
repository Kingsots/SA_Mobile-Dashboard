"""
DIAGNOSTIC TEST 1: Feature Importance Analysis

Load current model (models/model_current.pkl) and analyze feature importance.
Print top 10 features by:
1. Weight (how often used in splits)
2. Gain (avg information gain per split)
3. Cover (avg samples affected per split)

Flag features with >30% importance as HIGH RISK.
"""

import pickle
import pandas as pd
from pathlib import Path

print("=" * 70)
print("DIAGNOSTIC TEST 1: FEATURE IMPORTANCE ANALYSIS")
print("=" * 70)

# Load model - try current first, then shadow
model_path = Path("data/models/model_current.pkl")
if not model_path.exists():
    model_path = Path("data/models/model_shadow.pkl")
if not model_path.exists():
    print(f"❌ Model not found at data/models/")
    exit(1)

try:
    with open(model_path, "rb") as f:
        model = pickle.load(f)
    print(f"✅ Model loaded: {model_path}")
except Exception as e:
    print(f"❌ Error loading model: {e}")
    exit(1)

# Get importance scores
try:
    importance_weight = model.get_booster().get_score(importance_type='weight')
    importance_gain = model.get_booster().get_score(importance_type='gain')
    importance_cover = model.get_booster().get_score(importance_type='cover')
    print(f"✅ Importance scores extracted")
except Exception as e:
    print(f"❌ Error extracting importance: {e}")
    exit(1)

# Sort and display
print("\n" + "=" * 70)
print("FEATURE IMPORTANCE (WEIGHT - Split Frequency)")
print("=" * 70)
weight_sorted = sorted(importance_weight.items(), key=lambda x: x[1], reverse=True)[:10]
for i, (feat, score) in enumerate(weight_sorted, 1):
    print(f"{i:2d}. {feat:20s} {score:8.2f}")

print("\n" + "=" * 70)
print("FEATURE IMPORTANCE (GAIN - Information Gain)")
print("=" * 70)
gain_sorted = sorted(importance_gain.items(), key=lambda x: x[1], reverse=True)[:10]
for i, (feat, score) in enumerate(gain_sorted, 1):
    pct = score * 100 if score < 1 else score
    print(f"{i:2d}. {feat:20s} {pct:8.4f}")

print("\n" + "=" * 70)
print("FEATURE IMPORTANCE (COVER - Sample Coverage)")
print("=" * 70)
cover_sorted = sorted(importance_cover.items(), key=lambda x: x[1], reverse=True)[:10]
for i, (feat, score) in enumerate(cover_sorted, 1):
    print(f"{i:2d}. {feat:20s} {score:8.2f}")

# Flag suspicious features
print("\n" + "=" * 70)
print("LEAKAGE DETECTION - HIGH RISK FEATURES")
print("=" * 70)

high_risk = ['open', 'high', 'low', 'close', 'obv', 'ad', 'vwap']
found_leakage = False

for feat in high_risk:
    if feat in importance_gain:
        gain_val = importance_gain[feat]
        if gain_val > 0.30:
            print(f"🚨 SEVERE LEAKAGE: {feat:20s} {gain_val*100:6.1f}% importance")
            found_leakage = True
        elif gain_val > 0.15:
            print(f"⚠️  MODERATE LEAKAGE: {feat:20s} {gain_val*100:6.1f}% importance")

if not found_leakage:
    print("✅ No severe leakage detected (all high-risk features < 30%)")

print("\n" + "=" * 70)
print("INTERPRETATION")
print("=" * 70)
print("""
HIGH RISK FEATURES (likely causing leakage):
  - open, high, low, close  → Direct OHLC prices
  - obv, ad, vwap           → Cumulative indicators using close

If these show >30% importance:
  ❌ Model is learning to predict next_close from current close
  ❌ Not suitable for real trading (circular logic)

SAFE FEATURES (lagged indicators):
  - ema_21, ema_100, rsi_14
  - volume_ratio, vwap_slope
  - volume_sma_20

Action: Remove high-risk features, retrain with indicators only.
""")
