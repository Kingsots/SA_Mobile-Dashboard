#!/usr/bin/env python3
"""Query all recent signals in the database."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.database import DatabaseManager
from core.config import Config

db = DatabaseManager()

# Get all signals (no symbol filter)
signals = db.get_recent_signals(limit=100)

print(f"\n{'='*120}")
print(f"{'RECENT SIGNALS - ALL SYMBOLS':^120}")
print(f"{'='*120}\n")

if signals:
    print(f"{'Symbol':<10} {'Signal':<10} {'Entry':<12} {'SL':<12} {'TP':<12} {'RR':<7} {'Timestamp':<20} {'Source':<20}")
    print(f"{'-'*120}")
    
    for sig in signals[:50]:
        ticker = sig.get('ticker', 'N/A')
        direction = sig.get('signal', 0)
        if direction == 1:
            direction_str = '🟢 BUY'
        elif direction == -1:
            direction_str = '🔴 SELL'
        else:
            direction_str = '⚪ NEUTRAL'
        
        entry = f"{float(sig.get('entry_price', 0)):.4f}" if sig.get('entry_price') else '-'
        sl = f"{float(sig.get('stop_loss', 0)):.4f}" if sig.get('stop_loss') else '-'
        tp = f"{float(sig.get('take_profit', 0)):.4f}" if sig.get('take_profit') else '-'
        rr = f"{float(sig.get('risk_reward', 0)):.2f}" if sig.get('risk_reward') else '-'
        timestamp = sig.get('timestamp', 'N/A')[:20]
        source = sig.get('model_version', 'unknown')[:20]
        
        print(f"{ticker:<10} {direction_str:<10} {entry:<12} {sl:<12} {tp:<12} {rr:<7} {timestamp:<20} {source:<20}")
    
    print(f"\n{'='*120}")
    print(f"Total signals in database: {len(signals)}")
    print(f"{'='*120}\n")
else:
    print("❌ No signals found in database")
    print(f"{'='*120}\n")
