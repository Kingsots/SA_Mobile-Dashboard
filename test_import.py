#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/ubuntu/opticore-bot')

try:
    from signals.xgb_signal_engine import XGBSignalEngine
    print("✅ Signal engine imported successfully")
    
    # Test instantiation
    engine = XGBSignalEngine()
    print(f"✅ Signal engine instantiated")
    print(f"   Model loaded: {engine.model is not None}")
    print(f"   Metadata loaded: {engine.model_metadata is not None}")
    if engine.model_metadata:
        features = engine.model_metadata.get('features', [])
        print(f"   Expected features ({len(features)}): {features[:5]}...")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
