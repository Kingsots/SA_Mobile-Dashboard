#!/usr/bin/env python3
"""
Debug data types and database issues
"""

import pandas as pd
import sqlite3
from datetime import datetime

def debug_data_types():
    # Check what type of timestamps we're dealing with
    db_path = "trading_bot.db"
    
    try:
        # Check the latest data in the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if we have any data
        cursor.execute("SELECT COUNT(*) FROM ohlcv_data")
        count = cursor.fetchone()[0]
        print(f"Total records in database: {count}")
        
        if count > 0:
            # Check the structure of the timestamp column
            cursor.execute("SELECT timestamp FROM ohlcv_data LIMIT 5")
            samples = cursor.fetchall()
            print("Sample timestamps from database:")
            for sample in samples:
                print(f"  {sample[0]} (type: {type(sample[0])})")
        
        conn.close()
        
    except Exception as e:
        print(f"Error checking database: {e}")

def test_timestamp_conversion():
    # Test timestamp conversion
    print("\nTesting timestamp conversion:")
    
    # Create a sample timestamp
    sample_ts = pd.Timestamp('2023-08-01 12:00:00')
    print(f"Original timestamp: {sample_ts} (type: {type(sample_ts)})")
    
    # Test conversion methods
    try:
        py_datetime = sample_ts.to_pydatetime()
        print(f"to_pydatetime(): {py_datetime} (type: {type(py_datetime)})")
    except Exception as e:
        print(f"to_pydatetime() failed: {e}")
    
    try:
        iso_format = sample_ts.isoformat()
        print(f"isoformat(): {iso_format} (type: {type(iso_format)})")
    except Exception as e:
        print(f"isoformat() failed: {e}")
    
    try:
        str_format = str(sample_ts)
        print(f"str(): {str_format} (type: {type(str_format)})")
    except Exception as e:
        print(f"str() failed: {e}")

if __name__ == "__main__":
    debug_data_types()
    test_timestamp_conversion()