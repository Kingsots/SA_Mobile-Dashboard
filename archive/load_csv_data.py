#!/usr/bin/env python3
"""
Load CSV data into database
"""

import pandas as pd
import sqlite3
from datetime import datetime, timedelta

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

def load_csv_data():
    """Load data from CSV files into database"""
    print("📂 Loading CSV data into database...")
    
    csv_files = {
        "US30": "US30_1H_MASTER.csv",
        # Add other CSV files if you have them
        # "XAUUSD": "XAUUSD_1h.csv",
        # "USDJPY": "USDJPY_1h.csv",
    }
    
    db_manager = FixedDatabaseManager()
    
    for symbol, csv_file in csv_files.items():
        print(f"\n📊 Loading {symbol} from {csv_file}...")
        
        try:
            # Read CSV file
            df = pd.read_csv(csv_file)
            
            # Rename columns to match our expected format
            df = df.rename(columns={
                'Datetime': 'timestamp',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
            
            # Keep only the required columns
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            # Filter for the last 30 days
            cutoff_date = datetime.now() - timedelta(days=30)
            df = df[df.index >= cutoff_date]
            
            # Save to database
            db_manager.save_ohlcv_data(symbol, df, "csv")
            print(f"  ✅ Loaded {len(df)} periods for {symbol}")
            
        except Exception as e:
            print(f"  ❌ Error loading {symbol}: {e}")
    
    print("\n✅ CSV data loading completed!")

if __name__ == "__main__":
    load_csv_data()