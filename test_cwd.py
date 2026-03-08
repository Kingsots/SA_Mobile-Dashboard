#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, '/home/ubuntu/opticore-bot')

print(f"Current working directory: {os.getcwd()}")
print(f"Script location: {__file__}")

from core.config import Config
print(f"Config.DB_PATH: {Config.DB_PATH}")

import sqlite3
db_path_to_use = Config.DB_PATH

# Resolve to absolute path
if not os.path.isabs(db_path_to_use):
    db_path_to_use = os.path.join(os.getcwd(), db_path_to_use)

print(f"Resolved DB path: {db_path_to_use}")
print(f"Exists: {os.path.exists(db_path_to_use)}")

if os.path.exists(db_path_to_use):
    size = os.path.getsize(db_path_to_use)
    print(f"Size: {size} bytes")
    
    # Count rows
    conn = sqlite3.connect(db_path_to_use)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM ohlcv_data")
    ohlcv_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM ml_signals")
    signals_count = cursor.fetchone()[0]
    conn.close()
    
    print(f"ohlcv_data rows: {ohlcv_count}")
    print(f"ml_signals rows: {signals_count}")
