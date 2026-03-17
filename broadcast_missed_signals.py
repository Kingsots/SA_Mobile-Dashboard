#!/usr/bin/env python3
"""
Broadcast missed signals from the 12:35 UTC sweep to Telegram.
These 4 signals were built and validated but never sent to Telegram.
"""

import sys
sys.path.insert(0, '/home/ubuntu/SilentAnalyst')

import sqlite3
from signals.xgb_signal_engine_ec2 import PureStrategyEngine

# Initialize signal engine for broadcasting
signal_engine = PureStrategyEngine()

# Connect directly to database (trading_bot.db has ml_signals)
db_path = '/home/ubuntu/SilentAnalyst/trading_bot.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Query the 4 missed signals from 12:35 UTC
print("🔍 Fetching missed signals from database...")

query = """
SELECT trade_id, ticker, interval, signal, entry_price, stop_loss, take_profit, 
       risk_reward, timestamp, source, created_at
FROM ml_signals
WHERE created_at >= '2026-03-09 12:34:00' AND created_at <= '2026-03-09 12:36:00'
AND (ticker IN ('USDJPY', 'USDCAD', 'EURJPY', 'AUDCAD'))
ORDER BY created_at ASC
"""

try:
    cursor.execute(query)
    results = cursor.fetchall()
    
    if not results:
        print("❌ No signals found in database for this timeframe")
        sys.exit(1)
    
    print(f"✅ Found {len(results)} missed signals\n")
    
    # Broadcast each one
    for row in results:
        trade_id = row['trade_id'] if row['trade_id'] else 'unknown'
        ticker = row['ticker']
        interval = row['interval']
        signal_dir = row['signal']
        entry = row['entry_price']
        sl = row['stop_loss']
        tp = row['take_profit']
        rr = row['risk_reward']
        ts = row['timestamp']
        source = row['source']
        
        # Convert signal direction to label
        if signal_dir == 1:
            signal_label = "BUY"
            emoji = "🟢"
        elif signal_dir == -1:
            signal_label = "SELL"
            emoji = "🔴"
        else:
            signal_label = "NEUTRAL"
            emoji = "⚪"
        
        # Build signal_data dict for broadcast
        signal_data = {
            'ticker': ticker,
            'interval': interval,
            'signal': signal_dir,
            'signal_label': signal_label,
            'entry_price': entry,
            'stop_loss': sl,
            'take_profit': tp,
            'risk_reward': rr,
            'timestamp': str(ts),
            'trade_id': trade_id,
            'source': source,
        }
        
        print(f"📤 Broadcasting: {emoji} {ticker}-{interval} {signal_label} @ {entry:.4f}")
        print(f"   Entry={entry:.4f} | SL={sl:.4f} | TP={tp:.4f} | RR={rr:.2f}")
        
        # Send to Telegram
        try:
            signal_engine.broadcast_trade_signal(signal_data)
            print(f"   ✅ Sent to Telegram\n")
        except Exception as e:
            print(f"   ❌ Failed: {e}\n")
    
    print("✅ All missed signals broadcast to Telegram!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    conn.close()
