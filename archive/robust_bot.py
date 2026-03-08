#!/usr/bin/env python3
"""
Robust Trading Bot with multiple fallbacks
"""

import os
import sys
import time
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

print("🚀 Robust Trading Bot - Starting...")
print("=" * 50)

# Configuration
class Config:
    TRADING_PAIRS = {
        "US30": {"name": "Dow Jones", "csv_file": "US30_1H_MASTER.csv"},
        "XAUUSD": {"name": "Gold", "csv_file": "XAUUSD_1h.csv"},
        "USDJPY": {"name": "USD/JPY", "csv_file": "USDJPY_1h.csv"},
    }
    DB_PATH = "trading_bot.db"
    LOOKBACK_DAYS = 30

# Database Manager
class DatabaseManager:
    def __init__(self, db_path=Config.DB_PATH):
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
        print(f"✅ Database initialized")

    def save_ohlcv_data(self, symbol, df, source):
        """Save OHLCV data to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for index, row in df.iterrows():
            try:
                cursor.execute('''
                INSERT OR IGNORE INTO ohlcv_data 
                (symbol, timestamp, open, high, low, close, volume, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol, 
                    index,
                    row['open'],
                    row['high'],
                    row['low'],
                    row['close'],
                    int(row.get('volume', 0)),
                    source
                ))
            except Exception as e:
                print(f"❌ Error saving {symbol} data: {e}")
        
        conn.commit()
        conn.close()

# Data Fetcher with multiple fallbacks
class RobustDataFetcher:
    def __init__(self):
        self.db = DatabaseManager()
    
    def fetch_data(self, symbol_config, lookback_days=30):
        symbol_name = symbol_config["name"]
        csv_file = symbol_config.get("csv_file")
        
        print(f"\n📊 Fetching {symbol_name}...")
        
        # Try CSV file first
        if csv_file and Path(csv_file).exists():
            try:
                print(f"  Trying CSV file: {csv_file}")
                df = pd.read_csv(csv_file)
                
                # Standardize column names
                df = df.rename(columns={
                    'Date': 'timestamp', 'Open': 'open', 'High': 'high', 
                    'Low': 'low', 'Close': 'close', 'Volume': 'volume'
                })
                
                # Ensure timestamp column exists
                if 'timestamp' not in df.columns:
                    print("  ❌ No timestamp column found in CSV")
                    return None
                
                # Convert timestamp and set as index
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.set_index('timestamp')
                
                # Filter for the lookback period
                cutoff_date = datetime.now() - timedelta(days=lookback_days)
                df = df[df.index >= cutoff_date]
                
                # Ensure we have the required columns
                required_cols = ['open', 'high', 'low', 'close']
                for col in required_cols:
                    if col not in df.columns:
                        print(f"  ❌ Missing required column: {col}")
                        return None
                
                # Add volume if missing
                if 'volume' not in df.columns:
                    df['volume'] = 0
                
                print(f"  ✅ Loaded {len(df)} periods from CSV")
                self.db.save_ohlcv_data(symbol_name, df, "csv")
                return df
                
            except Exception as e:
                print(f"  ❌ CSV load failed: {e}")
        
        # Try Yahoo Finance as fallback
        print("  Trying Yahoo Finance...")
        try:
            import yfinance as yf
            
            # Map our symbols to Yahoo symbols
            yahoo_symbols = {
                "Dow Jones": "^DJI",
                "Gold": "GC=F", 
                "USD/JPY": "JPY=X"
            }
            
            yahoo_symbol = yahoo_symbols.get(symbol_name)
            if not yahoo_symbol:
                print(f"  ❌ No Yahoo symbol mapping for {symbol_name}")
                return None
            
            ticker = yf.Ticker(yahoo_symbol)
            df = ticker.history(period=f"{lookback_days}d", interval="1h")
            
            if df is None or df.empty:
                print(f"  ❌ No data from Yahoo Finance")
                return None
            
            df = df.reset_index()
            df = df.rename(columns={'Date': 'timestamp', 'Open': 'open', 'High': 'high', 
                                  'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
            
            print(f"  ✅ Loaded {len(df)} periods from Yahoo Finance")
            self.db.save_ohlcv_data(symbol_name, df, "yahoo")
            return df
            
        except Exception as e:
            print(f"  ❌ Yahoo Finance failed: {e}")
            return None

# Main Trading Bot
class TradingBot:
    def __init__(self):
        self.data_fetcher = RobustDataFetcher()
        print("✅ Trading bot initialized!")
    
    def backfill_data(self):
        print(f"\n📥 Backfilling {Config.LOOKBACK_DAYS} days of data...")
        for symbol, config in Config.TRADING_PAIRS.items():
            df = self.data_fetcher.fetch_data(config, Config.LOOKBACK_DAYS)
            time.sleep(1)

# Command Line Interface
def show_help():
    print("\n🤖 AI Trading Bot - Command Help")
    print("=" * 40)
    print("python robust_bot.py backfill - Backfill historical data")
    print("python robust_bot.py help - Show this help")

def main():
    if len(sys.argv) < 2:
        show_help()
        return
    
    command = sys.argv[1].lower()
    bot = TradingBot()
    
    if command == "backfill":
        bot.backfill_data()
    elif command == "help":
        show_help()
    else:
        print(f"❌ Unknown command: {command}")
        show_help()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")