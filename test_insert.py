import sqlite3
import sys

try:
    conn = sqlite3.connect(trading_bot.db)
    c = conn.cursor()
    
    # Get table info
    c.execute(PRAGMA table_info(strategy_state))
    cols = c.fetchall()
    print(fTable columns: {len(cols)} columns)
    for col in cols:
        print(f {col})
    
    # Try insert
    c.execute("
 INSERT OR REPLACE INTO strategy_state
 (ticker, interval, strategy_name, bull_extreme_visited, bear_extreme_visited, last_updated)
 VALUES (?, ?, ?, ?, ?, datetime( now))
 ", (TEST, 30m, strategy_core_v2, 1, 0))
    conn.commit()
    print(INSERT SUCCESS) 
except Exception as e:
    print(fERROR: {e})
    import traceback
    traceback.print_exc()
