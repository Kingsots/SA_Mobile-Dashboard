#!/usr/bin/env python3
"""
Fixed Database Manager with proper timestamp handling
"""

import sqlite3
import pandas as pd
from datetime import datetime

class FixedDatabaseManager:
    def __init__(self, db_path="trading_bot.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ohlcv_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume INTEGER,
            source TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, timestamp)
        )
        ''')
        conn.commit()
        conn.close()
        print(f"✅ Database initialized at {self.db_path}")
    
    def save_ohlcv_data(self, symbol, df, source):
        """Save OHLCV data to database with proper timestamp handling"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        success_count = 0
        error_count = 0
        
        for index, row in df.iterrows():
            try:
                # Convert timestamp to a format SQLite can handle
                if hasattr(index, 'to_pydatetime'):
                    timestamp = index.to_pydatetime()
                elif hasattr(index, 'timestamp'):
                    timestamp = datetime.fromtimestamp(index.timestamp())
                else:
                    timestamp = pd.to_datetime(index)
                    if hasattr(timestamp, 'to_pydatetime'):
                        timestamp = timestamp.to_pydatetime()
                
                cursor.execute('''
                INSERT OR IGNORE INTO ohlcv_data 
                (symbol, timestamp, open, high, low, close, volume, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol, 
                    timestamp,
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    int(row.get('volume', 0)),
                    source
                ))
                success_count += 1
            except Exception as e:
                error_count += 1
                if error_count <= 5:  # Only show first 5 errors to avoid spam
                    print(f"❌ Error saving {symbol} data: {e}")
        
        conn.commit()
        conn.close()
        
        if success_count > 0:
            print(f"  ✅ Successfully saved {success_count} records for {symbol}")
        if error_count > 0:
            print(f"  ❌ Failed to save {error_count} records for {symbol}")

# Test the fixed database manager
def test_fixed_manager():
    print("Testing fixed database manager...")
    
    # Create some sample data
    dates = pd.date_range('2023-08-01', periods=5, freq='D')
    sample_df = pd.DataFrame({
        'open': [100, 101, 102, 103, 104],
        'high': [101, 102, 103, 104, 105],
        'low': [99, 100, 101, 102, 103],
        'close': [100.5, 101.5, 102.5, 103.5, 104.5],
        'volume': [1000, 2000, 3000, 4000, 5000]
    }, index=dates)
    
    # Test saving
    db_manager = FixedDatabaseManager()
    db_manager.save_ohlcv_data("TEST", sample_df, "test")
    
    print("Test completed!")

if __name__ == "__main__":
    test_fixed_manager()