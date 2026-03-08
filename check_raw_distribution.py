import sys
sys.path.insert(0, '/home/ubuntu/SilentAnalyst')

import numpy as np
import sqlite3

print("\n" + "=" * 80)
print("FULL HISTORICAL DATASET - RAW CLASS DISTRIBUTION")
print("=" * 80)

try:
    # Connect to database
    conn = sqlite3.connect('/home/ubuntu/SilentAnalyst/trading_bot.db')
    cursor = conn.cursor()
    
    # Get ALL ml_signals (the training/historical data)
    cursor.execute("""
        SELECT signal FROM ml_signals
    """)
    
    all_signals = np.array([row[0] for row in cursor.fetchall()])
    
    print(f"\nTotal signals in database: {len(all_signals)}")
    
    # Get unique values and counts
    unique, counts = np.unique(all_signals, return_counts=True)
    
    print("\nRaw signal distribution (before any filtering):")
    print("-" * 80)
    
    total = len(all_signals)
    for label, count in zip(unique, counts):
        pct = 100 * count / total
        signal_name = {-1: 'SELL', 0: 'NEUTRAL', 1: 'BUY'}.get(label, f"Unknown ({label})")
        print(f"  {signal_name:12}: {count:6d} ({pct:6.2f}%)")
    
    print("\n" + "-" * 80)
    print(f"Total: {total}")
    
    # Check time range
    cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM ml_signals")
    min_time, max_time = cursor.fetchone()
    print(f"\nTime range: {min_time} to {max_time}")
    
    # Check sources
    cursor.execute("SELECT triggered_by, COUNT(*) FROM ml_signals GROUP BY triggered_by")
    print(f"\nSignals by source:")
    for source, count in cursor.fetchall():
        pct = 100 * count / total
        print(f"  {source:40}: {count:6d} ({pct:6.2f}%)")
    
    conn.close()

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
