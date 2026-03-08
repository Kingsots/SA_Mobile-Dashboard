#!/usr/bin/env python3
"""
Phase 2 Test - Manually trigger signal generation to test Phase 2 logging
"""

import sys
import os

sys.path.insert(0, '/home/ubuntu/SilentAnalyst')
os.chdir('/home/ubuntu/SilentAnalyst')

# Set environment
os.environ['TIINGO_API_TOKEN'] = '721e7de39daa4eaf3f119bbbee55ba64a8d700eb'

try:
    from signals.xgb_signal_engine_ec2 import XGBSignalEngine
    from core.database import DatabaseManager
    from core.config import Config
    from features.engine import FeatureEngine
    
    print("[1] Initializing engines...")
    db = DatabaseManager()
    feature_engine = FeatureEngine(db)
    signal_engine = XGBSignalEngine(db, feature_engine)
    
    print("[2] Running signal generation for 30m interval...")
    signal_engine.generate_signals(interval='30m')
    
    print("[3] Checking Phase 2 log file...")
    phase2_log = '/home/ubuntu/SilentAnalyst/logs/phase2_comparison.log'
    if os.path.exists(phase2_log):
        with open(phase2_log) as f:
            lines = f.readlines()
        print(f"✓ Phase 2 log created with {len(lines)} entries")
        print("\nSample entries:")
        for line in lines[-5:]:
            print(line.strip())
    else:
        print("✗ Phase 2 log NOT created - debugging...")
        
        # Check if strategy_core is available
        try:
            from core.strategy_core import evaluate
            print("✓ strategy_core imported successfully")
        except Exception as e:
            print(f"✗ strategy_core import failed: {e}")
            
        # Check signal_debug log
        signal_debug = '/home/ubuntu/SilentAnalyst/logs/signal_debug.log'
        print(f"\nLast 10 lines of signal_debug.log:")
        os.system(f'tail -10 {signal_debug}')
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
