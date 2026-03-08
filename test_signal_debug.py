#!/usr/bin/env python3
"""Debug signal generation after deployment"""

from signals.xgb_signal_engine import XGBSignalEngine
from core.config import Config

print("=" * 60)
print("SIGNAL GENERATION DEBUG")
print("=" * 60)

engine = XGBSignalEngine()
print(f"\n✅ Engine initialized")
print(f"   Model version: {engine.model_version}")
print(f"   Feature columns: {len(engine.feature_cols)}")
print(f"   Confidence threshold: {Config.ML_SIGNAL_CONFIDENCE_MIN}")

# Try EURGBP 4h (the one that had signal at 9:00)
print("\n" + "=" * 60)
print("Testing EURGBP 4h...")
print("=" * 60)

result = engine.generate_signal('EURGBP', '4h')
if result:
    print(f"✅ Signal generated:")
    print(f"   Signal: {result.get('signal')} (1=BUY, -1=SELL, 0=NEUTRAL)")
    print(f"   Confidence: {result.get('confidence'):.2%}")
    print(f"   Entry price: {result.get('entry_price')}")
    print(f"   Entry source: {result.get('entry_source')}")
else:
    print("❌ No signal generated (result is None)")

# Try another pair
print("\n" + "=" * 60)
print("Testing GBPUSD 4h...")
print("=" * 60)

result2 = engine.generate_signal('GBPUSD', '4h')
if result2:
    print(f"✅ Signal generated:")
    print(f"   Signal: {result2.get('signal')} (1=BUY, -1=SELL, 0=NEUTRAL)")
    print(f"   Confidence: {result2.get('confidence'):.2%}")
    print(f"   Entry price: {result2.get('entry_price')}")
else:
    print("❌ No signal generated (result is None)")

print("\nDone.")
