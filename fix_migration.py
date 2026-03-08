#!/usr/bin/env python3
"""Quick fix to complete the migration"""
import sqlite3
import os

# Get database path
db_path = os.path.join(os.path.dirname(__file__), 'data', 'trading_bot.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Creating api_usage table...")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS api_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        api_name TEXT NOT NULL,
        endpoint TEXT,
        ticker TEXT,
        interval TEXT,
        success INTEGER DEFAULT 1,
        error_message TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")

cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_api_usage_timestamp 
    ON api_usage(timestamp)
""")

cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_api_usage_api_name 
    ON api_usage(api_name)
""")

print("✅ api_usage table created")

print("\nCreating model_training_log table...")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS model_training_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        model_version TEXT NOT NULL,
        train_samples INTEGER,
        test_samples INTEGER,
        accuracy REAL,
        metrics TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")

cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_model_training_timestamp 
    ON model_training_log(timestamp)
""")

print("✅ model_training_log table created")

print("\nCreating rate_limits table...")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS rate_limits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        api_name TEXT NOT NULL UNIQUE,
        requests_made INTEGER DEFAULT 0,
        reset_time TEXT NOT NULL,
        limit_per_hour INTEGER NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")

cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_rate_limits_api_name 
    ON rate_limits(api_name)
""")

print("✅ rate_limits table created")

conn.commit()
conn.close()

print("\n✅ All tables created successfully!")
