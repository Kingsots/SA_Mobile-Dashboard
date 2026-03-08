#!/usr/bin/env python3
"""
Manual Phase 2 test trigger
Forces signal generation for a single symbol to test Phase 2 logging
"""
import sys
import os

sys.path.insert(0, '/home/ubuntu/SilentAnalyst')
os.chdir('/home/ubuntu/SilentAnalyst')

# Set API token
os.environ['TIINGO_API_TOKEN'] = '721e7de39daa4eaf3f119bbbee55ba64a8d700eb'

print("\n" + "="*70)
print("🧪 MANUAL PHASE 2 TEST TRIGGER")
print("="*70 + "\n")

try:
    from signals.xgb_signal_engine_ec2 import XGBSignalEngine
    from signals.event_filter import MarketEvent
    from datetime import datetime, timezone
    
    print("[1] Initializing signal engine...")
    se = XGBSignalEngine()
    print("    ✅ Engine ready")
    
    print("\n[2] Creating test event...")
    # Create a fake event to trigger signal generation
    test_event = MarketEvent(
        ticker="EURUSD",
        interval="30m",
        event_type="rsi_rebound_bullish",
        confidence=0.75,
        timestamp=datetime.now(timezone.utc).isoformat(),
        details={"prev_rsi": 30, "current_rsi": 40, "period": 14}
    )
    print(f"    ✅ Test event created: {test_event.ticker} {test_event.interval} {test_event.event_type}")
    
    print("\n[3] Generating signal for test event...")
    signal_data = se.generate_signal(
        ticker=test_event.ticker,
        interval=test_event.interval,
        event=test_event,
        metadata={"source": "manual_test", "test": True}
    )
    
    if signal_data:
        print(f"    ✅ Signal generated: {signal_data['signal_label']}")
        print(f"       Confidence: {signal_data['confidence']:.1%}")
    else:
        print(f"    ⚠️  No signal (feature prep failed - expected)")
    
    print("\n[4] Checking Phase 2 log file...")
    import time
    time.sleep(1)
    
    phase2_log = '/home/ubuntu/SilentAnalyst/logs/phase2_comparison.log'
    if os.path.exists(phase2_log):
        with open(phase2_log) as f:
            lines = f.readlines()
        
        print(f"    ✅ PHASE 2 LOG EXISTS: {len(lines)} entries")
        print("\n    📋 Last 3 entries:")
        for line in lines[-3:]:
            import json
            try:
                entry = json.loads(line)
                print(f"       • {entry['ticker']} {entry['interval']}: core={entry['core_signal']}, ml={entry['ml_signal']}, match={entry['match']}")
            except:
                print(f"       • {line[:100]}")
                
        print("\n    ✅ SUCCESS: Phase 2 logging is working!")
    else:
        print(f"    ❌ PHASE 2 LOG NOT FOUND")
        print(f"       Expected: {phase2_log}")
        print("       This means Phase 2 comparison never ran")
        
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("🧪 TEST COMPLETE")
print("="*70 + "\n")
