#!/usr/bin/env python3
"""
Quick test to manually trigger signal generation and check for errors
"""
import sys
import os
sys.path.insert(0, '/home/ubuntu/opticore-bot')

from signals.xgb_signal_engine import XGBSignalEngine
from core.config import Config

print("=" * 70)
print("🧪 MANUAL SIGNAL GENERATION TEST")
print("=" * 70)

try:
    engine = XGBSignalEngine()
    print(f"\n✅ Signal engine initialized")
    print(f"   Model: {engine.model_version}")
    print(f"   Accuracy: {engine.model_accuracy:.2%}" if engine.model_accuracy else "   Model: Not loaded")
    
    print(f"\n📊 Generating signals for 1h interval...")
    result = engine.generate_signals('1h')
    
    if result:
        signals_generated = len([s for s in result.values() if s])
        print(f"\n✅ {signals_generated} signals generated successfully!")
        for ticker, signal_data in list(result.items())[:3]:
            if signal_data:
                print(f"   {ticker}: {signal_data.get('signal_label', 'UNKNOWN')} (confidence: {signal_data.get('confidence', 0):.1%})")
    else:
        print(f"\n⚠️  No signals returned")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
