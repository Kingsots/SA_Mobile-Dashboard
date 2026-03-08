#!/usr/bin/env python3
"""
Quick Data Fetcher for Today's Alerts - Fixed Version
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

def fetch_todays_data():
    """Fetch minimal data needed for today's alerts"""
    print("📥 Fetching today's data...")
    
    # List of symbols to fetch
    symbols = {
        "US30": "^DJI",
        "XAUUSD": "GC=F", 
        "USDJPY": "JPY=X",
        "GBPUSD": "GBPUSD=X",
        "EURJPY": "EURJPY=X",
        "AUDCAD": "AUDCAD=X"
    }
    
    db_manager = FixedDatabaseManager()
    
    for name, symbol in symbols.items():
        print(f"\n📊 Fetching {name} ({symbol})...")
        
        try:
            import yfinance as yf
            
            # Fetch data for the last 30 days
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="30d", interval="1h")
            
            if df is None or df.empty:
                print(f"  ❌ No data for {symbol}")
                continue
            
            df = df.reset_index()
            df = df.rename(columns={'Date': 'timestamp', 'Open': 'open', 'High': 'high', 
                                  'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
            
            # Save to database
            db_manager.save_ohlcv_data(name, df, "yahoo")
            print(f"  ✅ Saved {len(df)} periods for {name}")
            
        except Exception as e:
            print(f"  ❌ Error fetching {name}: {e}")
    
    print("\n✅ Data fetch completed!")

if __name__ == "__main__":
    fetch_todays_data()