#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, '/home/ubuntu/opticore-bot')

print(f"CWD: {os.getcwd()}")

from core.database import DatabaseManager

db = DatabaseManager()
print(f"DatabaseManager.db_path: {db.db_path}")

# Now try to load
df = db.load_ohlcv_data('XAUUSD', '1h', limit=50)
print(f"load_ohlcv_data result: {df is not None}")
if df is not None:
    print(f"DataFrame shape: {df.shape}")
    print(f"Latest timestamp: {df.index[-1]}")
else:
    print("Result is None!")
