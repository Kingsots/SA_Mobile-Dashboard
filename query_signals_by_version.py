#!/usr/bin/env python3
"""
Query signals by strategy version (V1 vs V2)
Shows signal distribution by engine source
"""

import sys
sys.path.insert(0, '/home/ubuntu/SilentAnalyst')

import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict

def query_signals_by_version(hours=24):
    """Query signals from the last N hours, grouped by strategy version"""
    
    db_path = '/home/ubuntu/SilentAnalyst/trading_bot.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Calculate time window
    cutoff_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    
    print(f"\n{'='*80}")
    print(f"📊 SIGNAL DISTRIBUTION - Last {hours} hours")
    print(f"{'='*80}\n")
    
    # Query total counts by strategy version
    cursor.execute("""
        SELECT strategy_version, COUNT(*) as count, 
               SUM(CASE WHEN signal = 1 THEN 1 ELSE 0 END) as buy_count,
               SUM(CASE WHEN signal = -1 THEN 1 ELSE 0 END) as sell_count,
               AVG(confidence) as avg_confidence
        FROM ml_signals 
        WHERE timestamp > ?
        GROUP BY strategy_version
        ORDER BY strategy_version DESC
    """, (cutoff_time,))
    
    results = cursor.fetchall()
    
    if not results:
        print("No signals found in the specified time period")
        return
    
    for version, total, buys, sells, avg_conf in results:
        version_label = "🟢 V1 (Core Engine)" if version == 'v1' else "🔵 V2 (State Machine)"
        print(f"{version_label}")
        print(f"  Total Signals: {total}")
        print(f"  BUY Signals:  {buys or 0}")
        print(f"  SELL Signals: {sells or 0}")
        print(f"  Avg Confidence: {(avg_conf or 0):.2%}")
        print()
    
    # Query recent signals with details
    print(f"{'='*80}")
    print("📋 RECENT SIGNALS (Last 10)")
    print(f"{'='*80}\n")
    
    cursor.execute("""
        SELECT timestamp, ticker, signal, confidence, strategy_version, triggered_by
        FROM ml_signals 
        WHERE timestamp > ?
        ORDER BY timestamp DESC
        LIMIT 10
    """, (cutoff_time,))
    
    columns = ['Time', 'Symbol', 'Signal', 'Confidence', 'Engine', 'Type']
    print(f"{columns[0]:19} {columns[1]:10} {columns[2]:8} {columns[3]:12} {columns[4]:8} {columns[5]:10}")
    print("-" * 80)
    
    for row in cursor.fetchall():
        ts, ticker, signal, conf, version, trigger = row
        signal_emoji = "🟢 BUY " if signal == 1 else "🔴 SELL"
        version_tag = "V1" if version == 'v1' else "V2"
        print(f"{ts:19} {ticker:10} {signal_emoji:8} {conf:12.2%} {version_tag:8} {trigger:10}")
    
    print()
    
    # Summary by symbol
    print(f"{'='*80}")
    print("🎯 SIGNALS BY SYMBOL (All time)")
    print(f"{'='*80}\n")
    
    cursor.execute("""
        SELECT ticker, strategy_version, COUNT(*) as count,
               AVG(confidence) as avg_confidence
        FROM ml_signals
        GROUP BY ticker, strategy_version
        ORDER BY ticker, strategy_version DESC
    """)
    
    print(f"{'Symbol':10} {'V1 Count':10} {'V2 Count':10} {'V1 Avg Conf':15} {'V2 Avg Conf':15}")
    print("-" * 80)
    
    # Group results by symbol
    symbol_data = defaultdict(lambda: {'v1': 0, 'v2': 0, 'v1_conf': 0, 'v2_conf': 0})
    
    cursor.execute("""
        SELECT ticker, strategy_version, COUNT(*) as count,
               AVG(confidence) as avg_confidence
        FROM ml_signals
        GROUP BY ticker, strategy_version
        ORDER BY ticker, strategy_version DESC
    """)
    
    for ticker, version, count, avg_conf in cursor.fetchall():
        if version == 'v1':
            symbol_data[ticker]['v1'] = count
            symbol_data[ticker]['v1_conf'] = avg_conf or 0
        else:
            symbol_data[ticker]['v2'] = count
            symbol_data[ticker]['v2_conf'] = avg_conf or 0
    
    for symbol in sorted(symbol_data.keys()):
        data = symbol_data[symbol]
        print(f"{symbol:10} {data['v1']:10} {data['v2']:10} {data['v1_conf']:14.2%} {data['v2_conf']:15.2%}")
    
    print()
    conn.close()

if __name__ == '__main__':
    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    query_signals_by_version(hours)
