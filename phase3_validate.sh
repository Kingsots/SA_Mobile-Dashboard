#!/bin/bash
cd /home/ubuntu/SilentAnalyst
source venv/bin/activate

echo "=== PHASE 3 FINAL VALIDATION ==="
echo ""
echo "=== STEP 1: Verify core imports ==="
python3 << 'ENDPYTHON'
import pandas
import aiohttp
import apscheduler
import xgboost
import scikit
print("✅ Core packages OK")
ENDPYTHON

echo ""
echo "=== STEP 2: Full syntax validation ==="
python3 -m py_compile async_scheduler.py && echo "✅ async_scheduler.py" || echo "❌ async_scheduler.py FAILED"
python3 -m py_compile core/strategy_core_v1.py && echo "✅ strategy_core_v1.py" || echo "❌ strategy_core_v1.py FAILED"
python3 -m py_compile core/strategy_core_v2.py && echo "✅ strategy_core_v2.py" || echo "❌ strategy_core_v2.py FAILED"
python3 -m py_compile signals/xgb_signal_engine_ec2.py && echo "✅ xgb_signal_engine_ec2.py" || echo "❌ xgb_signal_engine_ec2.py FAILED"
python3 -m py_compile signals/trade_constructor.py && echo "✅ trade_constructor.py" || echo "❌ trade_constructor.py FAILED"

echo ""
echo "=== PHASE 3 COMPLETE ==="
echo "Location: $(pwd)"
echo "venv: $(which python3)"
