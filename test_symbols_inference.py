#!/usr/bin/env python3
"""Test model inference for multiple symbols - find which ones have data"""

import sys
sys.path.insert(0, "/home/ubuntu/SilentAnalyst")

from signals.xgb_signal_engine_ec2 import XGBSignalEngine
from core.config import Config

print("\n" + "="*70)
print("MULTI-SYMBOL MODEL INFERENCE TEST")
print("="*70 + "\n")

try:
    engine = XGBSignalEngine()
    print("✅ Engine initialized\n")
    
    engine.load_model()
    print("✅ Model loaded\n")
    
    # Test first 5 symbols from config
    symbols = Config.get_symbol_list()[:5]
    print(f"Testing {len(symbols)} symbols for 1h interval:\n")
    print("-" * 70)
    
    for symbol in symbols:
        print(f"\n📊 Testing {symbol}...")
        try:
            result = engine.generate_signal(symbol, "1h")
            
            if result:
                print(f"   ✅ Signal generated")
                print(f"      Signal: {result.get('signal_label')}")
                print(f"      Confidence: {result.get('confidence'):.4f}")
            else:
                print(f"   ❌ No signal (hard gate blocked - insufficient ddata)")
                
        except Exception as e:
            print(f"   ⚠️  Error: {str(e)[:100]}")
    
    print("\n" + "="*70)
    
except Exception as e:
    print(f"❌ FATAL ERROR: {e}")
    import traceback
    traceback.print_exc()
