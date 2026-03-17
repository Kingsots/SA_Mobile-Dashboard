#!/usr/bin/env python3
"""
Broadcast the 4 known missed signals directly to Telegram.
These signals were detected at 12:35 UTC but not broadcast.
"""

import sys
sys.path.insert(0, '/home/ubuntu/SilentAnalyst')

from signals.xgb_signal_engine_ec2 import PureStrategyEngine

# Initialize signal engine
signal_engine = PureStrategyEngine()

# The 4 missed signals with exact data from 12:35 UTC event
missed_signals = [
    {
        'ticker': 'USDJPY',
        'interval': '4h',
        'signal': -1,  # SELL
        'signal_label': 'SELL',
        'entry_price': 158.4288,
        'stop_loss': 158.9010,
        'take_profit': 157.4844,
        'risk_reward': 2.00,
        'trade_id': 'ee5995f2-967',
        'source': 'v2_persistence',
        'timestamp': '2026-03-09T12:35:00',
    },
    {
        'ticker': 'USDCAD',
        'interval': '30m',
        'signal': 1,  # BUY
        'signal_label': 'BUY',
        'entry_price': 1.3564,
        'stop_loss': 1.3526,
        'take_profit': 1.3642,
        'risk_reward': 2.00,
        'trade_id': '98c349bc-170',
        'source': 'v2_persistence',
        'timestamp': '2026-03-09T12:35:01',
    },
    {
        'ticker': 'EURJPY',
        'interval': '4h',
        'signal': 1,  # BUY
        'signal_label': 'BUY',
        'entry_price': 183.0156,
        'stop_loss': 182.3745,
        'take_profit': 184.2978,
        'risk_reward': 2.00,
        'trade_id': '1dfd896d-819',
        'source': 'v2_persistence',
        'timestamp': '2026-03-09T12:35:03',
    },
    {
        'ticker': 'AUDCAD',
        'interval': '1h',
        'signal': 1,  # BUY
        'signal_label': 'BUY',
        'entry_price': 0.9508,
        'stop_loss': 0.9474,
        'take_profit': 0.9577,
        'risk_reward': 2.00,
        'trade_id': 'cf917e6b-1b1',
        'source': 'v2_persistence',
        'timestamp': '2026-03-09T12:35:03',
    },
]

print("📤 Broadcasting 4 missed signals to Telegram...\n")

success_count = 0
for sig in missed_signals:
    print(f"📢 {sig['signal_label']} {sig['ticker']}-{sig['interval']} @ {sig['entry_price']}")
    print(f"   Entry={sig['entry_price']} | SL={sig['stop_loss']} | TP={sig['take_profit']} | RR={sig['risk_reward']:.2f}")
    
    try:
        signal_engine.broadcast_trade_signal(sig)
        print("   ✅ Sent to Telegram\n")
        success_count += 1
    except Exception as e:
        print(f"   ❌ Failed: {e}\n")

print(f"✅ Broadcast complete: {success_count}/4 signals sent")
