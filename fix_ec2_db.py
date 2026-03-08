#!/usr/bin/env python3
"""Fix EC2 database schema issues."""
import sqlite3
import os

DB_PATH = '/home/ubuntu/opticore-bot/data/trading_bot.db'

def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # List all tables
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in c.fetchall()]
    print(f"Tables in database: {tables}")
    
    # Check if rate_limits exists
    if 'rate_limits' not in tables:
        print("\n⚠️  rate_limits table missing - creating it...")
        c.execute('''
            CREATE TABLE rate_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_name TEXT NOT NULL,
                period TEXT NOT NULL,
                request_count INTEGER DEFAULT 0,
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ rate_limits table created")
    else:
        print("\n✅ rate_limits table exists")
    
    conn.commit()
    conn.close()
    print("\n✅ Database fixed successfully")

if __name__ == '__main__':
    main()
