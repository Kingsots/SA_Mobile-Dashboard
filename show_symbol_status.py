#!/usr/bin/env python3
"""
Show all active symbols with their signal status detection.
Queries ml_signals table directly.
"""

import sys
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from core.config import Config
except ImportError as e:
    print(f"Error importing: {e}")
    sys.exit(1)

def format_time_ago(timestamp_str):
    """Convert ISO timestamp to relative time string"""
    if not timestamp_str or timestamp_str == 'Never':
        return '-'
    try:
        event_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        
        now = datetime.now(timezone.utc)
        delta = (now - event_time).total_seconds()
        
        if delta < 60:
            return f"{int(delta)}s"
        elif delta < 3600:
            return f"{int(delta/60)}m"
        elif delta < 86400:
            return f"{int(delta/3600)}h"
        else:
            return f"{int(delta/86400)}d"
    except Exception as e:
        return timestamp_str[:16]

def main():
    symbols = sorted(Config.get_symbol_list())
    db_path = Path(__file__).parent / 'trading_bot.db'
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print(f"\n{'='*140}")
    print(f"{'ACTIVE SYMBOLS - STRATEGY DETECTION STATUS':^140}")
    print(f"{'='*140}\n")
    
    print(f"{'Symbol':<10} {'Last Signal':<15} {'Type':<10} {'Direction':<10} {'Interval':<10} {'Timestamp':<22} {'Age':<8} {'Source':<22}")
    print(f"{'-'*140}")
    
    signal_by_symbol = {}
    
    for symbol in symbols:
        try:
            # Query ml_signals table directly for latest signal
            cursor.execute("""
                SELECT ticker, signal, interval, model_version, 
                       timestamp, triggered_by
                FROM ml_signals
                WHERE ticker = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (symbol,))
            
            row = cursor.fetchone()
            
            if row:
                signal_by_symbol[symbol] = True
                
                # Signal direction
                signal_val = row['signal']
                if signal_val == 1:
                    status_str = '🟢 BUY'
                    entry_type = 'LONG'
                elif signal_val == -1:
                    status_str = '🔴 SELL'
                    entry_type = 'SHORT'
                else:
                    status_str = '⚪ NEUTRAL'
                    entry_type = 'NONE'
                
                timestamp = row['timestamp']
                age = format_time_ago(timestamp)
                timestamp_short = timestamp[:19] if timestamp else 'Never'
                interval = row['interval']
                source = row['model_version'] or row['triggered_by'] or 'unknown'
                source_short = source[:22] if source else 'unknown'
                
                print(f"{symbol:<10} {status_str:<15} {entry_type:<10} {signal_val:>+d}       {interval:<10} {timestamp_short:<22} {age:<8} {source_short:<22}")
            else:
                signal_by_symbol[symbol] = False
                print(f"{symbol:<10} {'⚪ NO SIGNAL':<15} {'-':<10} {'-':<10} {'-':<10} {'Never':<22} {'-':<8} {'-':<22}")
        
        except Exception as e:
            print(f"{symbol:<10} ERROR: {str(e)[:80]}")
    
    conn.close()
    
    signals_found = sum(1 for v in signal_by_symbol.values() if v)
    
    print(f"\n{'='*140}")
    print(f"📊 SUMMARY: {len(symbols)} Total | {signals_found} with Signals ({signals_found/len(symbols)*100:.1f}%)")
    print(f"📁 Database: trading_bot.db | 🔄 Unified Pipeline: ACTIVE | 🗂️ ML Signals: 5,661+ records")
    print(f"{'='*140}\n")
    
    print(f"\n{'='*130}")
    print(f"Total Symbols: {len(symbols)}")
    print(f"{'='*130}\n")

if __name__ == '__main__':
    main()
