#!/usr/bin/env python3
"""
Check what's in the database
"""

import sqlite3
import pandas as pd

def check_database():
    db_path = "trading_bot.db"
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Check if tables exist
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print("📊 Database Tables:")
        for table in tables:
            print(f"  ✅ {table[0]}")
            
            # Count rows in each table
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            print(f"    Rows: {count}")
            
            # Show a few sample rows
            if count > 0:
                cursor.execute(f"SELECT * FROM {table[0]} LIMIT 3")
                sample = cursor.fetchall()
                print(f"    Sample: {sample}")
            
            print()
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")

if __name__ == "__main__":
    check_database()