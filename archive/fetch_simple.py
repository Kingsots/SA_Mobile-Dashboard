#!/usr/bin/env python3
"""
Simple Data Fetcher - Working Version
"""

import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()  # Load environment variables

class SimpleDatabaseManager:
    def __init__(self, db_path="trading_bot.db"):
        self.db_path = db_path
    
    def save_data(self, symbol, df, source):
        """Simple data saving method"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for index, row in df.iterrows():
            try:
                # Convert timestamp to string format
                timestamp_str = index.strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute('''
                INSERT OR IGNORE INTO ohlcv_data 
                (symbol, timestamp, open, high, low, close, volume, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol, 
                    timestamp_str,
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    int(row.get('volume', 0)),
                    source
                ))
            except Exception as e:
                print(f"❌ Error saving {symbol} data: {e}")
        
        conn.commit()
        conn.close()
        print(f"  ✅ Saved data for {symbol}")

def fetch_simple_data():
    """Fetch simple data for testing"""
    print("📥 Fetching simple data...")
    
    # For now, let's just use the CSV data since Yahoo Finance is having issues
    print("⚠️ Yahoo Finance is having issues, using CSV data instead")
    
    # Run the fixed CSV loader
    import subprocess
    subprocess.run(["python", "load_csv_data_fixed.py"])
    
    print("✅ Data fetch completed!")

if __name__ == "__main__":
    fetch_simple_data()