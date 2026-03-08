#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/ubuntu/opticore-bot')
import sqlite3
import pandas as pd

# Direct database check
db_path = '/home/ubuntu/opticore-bot/trading_bot.db'
conn = sqlite3.connect(db_path)

# Check if table exists
tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table'", conn)
print("Tables in database:")
print(tables)

# Check row counts
counts = pd.read_sql_query("SELECT 'ohlcv_data' as table_name, COUNT(*) as rows FROM ohlcv_data UNION ALL SELECT 'ml_signals', COUNT(*) FROM ml_signals", conn)
print("\nRow counts:")
print(counts)

# Try to fetch XAUUSD 1h data directly
print("\n" + "="*60)
print("Querying ohlcv_data directly...")
df = pd.read_sql_query("SELECT * FROM ohlcv_data WHERE symbol='XAUUSD' AND timeframe='1h' LIMIT 5", conn)
print(f"Result shape: {df.shape}")
if not df.empty:
    print(f"Columns: {list(df.columns)}")
    print(f"Last row:\n{df.iloc[-1]}")
else:
    print("Result is EMPTY!")

conn.close()
