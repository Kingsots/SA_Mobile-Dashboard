#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/ubuntu/opticore-bot')
import sqlite3
import pandas as pd

db_path = '/home/ubuntu/opticore-bot/trading_bot.db'

# Replicate what load_ohlcv_data does
symbol = 'XAUUSD'
timeframe = '1h'
limit = 250

try:
    conn = sqlite3.connect(db_path)
    
    query = f'''
    SELECT timestamp, open, high, low, close, volume 
    FROM ohlcv_data 
    WHERE symbol = ? AND timeframe = ?
    ORDER BY timestamp DESC
    LIMIT {limit}
    '''
    
    print(f"Query: {query}")
    print(f"Params: {(symbol, timeframe)}")
    
    df = pd.read_sql_query(query, conn, params=(symbol, timeframe))
    conn.close()
    
    print(f"Result shape: {df.shape}")
    print(f"Is empty: {df.empty}")
    
    if not df.empty:
        print(f"First row timestamp: {df.iloc[0]['timestamp']}")
        print(f"Last row timestamp: {df.iloc[-1]['timestamp']}")
        
        # Convert timestamp to datetime and set as index
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')
        
        # Reverse for ASC order
        df = df.iloc[::-1]
        
        print(f"After processing shape: {df.shape}")
        print(f"SUCCESS - would return DataFrame with {len(df)} rows")
    else:
        print("Result is EMPTY - would return None")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
