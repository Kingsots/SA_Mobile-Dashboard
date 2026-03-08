#!/usr/bin/env python3
"""
AI Trading Bot - Clean Version
"""

import os
import sys
import time
import requests
import pandas as pd
import numpy as np
import sqlite3
import json
import io
from datetime import datetime, timedelta
from pathlib import Path

print("🚀 AI Trading Bot - Starting...")
print("=" * 50)

# Load environment variables
def load_env():
    env_path = Path('.env')
    if env_path.exists():
        print(f"✅ Loading .env file")
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    else:
        print(f"⚠️ No .env file found")

load_env()

# Configuration
class Config:
    TRADING_PAIRS = {
        "US30": {"name": "Dow Jones", "symbols": {"yahoo": "^DJI"}},
        "XAUUSD": {"name": "Gold", "symbols": {"yahoo": "GC=F"}},
        "USDJPY": {"name": "USD/JPY", "symbols": {"yahoo": "JPY=X"}},
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

# Market Data Fetcher
class MarketDataFetcher:
    def __init__(self):
        self.db = DatabaseManager()
    
    def fetch_data(self, symbol_config, lookback_days=30):
        try:
            import yfinance as yf
            symbol = symbol_config["symbols"]["yahoo"]
            print(f"  Fetching {symbol_config['name']} ({symbol})...")
            
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=f"{lookback_days}d", interval="1h")
            
            if df is None or df.empty:
                return None
            
            df = df.reset_index()
            df = df.rename(columns={'Date': 'timestamp', 'Open': 'open', 'High': 'high', 
                                  'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
            
            self.db.save_ohlcv_data(symbol_config["name"], df, "yahoo")
            print(f"  ✅ Saved {len(df)} periods")
            return df
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return None

# Main Trading Bot
class TradingBot:
    def __init__(self):
        self.data_fetcher = MarketDataFetcher()
        print("✅ Trading bot initialized!")
    
    def backfill_data(self):
        print(f"\n📥 Backfilling {Config.LOOKBACK_DAYS} days of data...")
        for symbol, config in Config.TRADING_PAIRS.items():
            print(f"\n📊 Backfilling {symbol} ({config['name']})...")
            df = self.data_fetcher.fetch_data(config, Config.LOOKBACK_DAYS)
            time.sleep(1)

# Command Line Interface
def show_help():
    print("\n🤖 AI Trading Bot - Command Help")
    print("=" * 40)
    print("python main_clean.py backfill - Backfill historical data")
    print("python main_clean.py help - Show this help")

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