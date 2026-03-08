#!/usr/bin/env python3
"""Manual EURUSD model inference test"""

import sys
sys.path.insert(0, "/home/ubuntu/SilentAnalyst")

from signals.xgb_signal_engine_ec2 import XGBSignalEngine

print("\n" + "="*70)
print("MANUAL MODEL INFERENCE TEST - EURUSD 1h")
print("="*70 + "\n")

try:
    engine = XGBSignalEngine()
    print("✅ Engine initialized")
    
    engine.load_model()
    print("✅ Model loaded\n")
    
    print("Running generate_signal for EURUSD 1h...\n")
    result = engine.generate_signal("EURUSD", "1h")
    
    print("\n" + "="*70)
    print("INFERENCE RESULT:")
    print("="*70)
    if result:
        print(f"Signal: {result.get('signal_label')}")
        print(f"Confidence: {result.get('confidence'):.4f}")
        print(f"Ticker: {result.get('ticker')}")
        print(f"Entry Price: {result.get('entry_price')}")
    else:
        print("❌ No signal returned (hard gate blocked - insufficient history)")
    print("="*70 + "\n")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
