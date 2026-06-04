#!/usr/bin/env python3
"""
Advanced Trading Bot with Multiple Data Sources
"""

import os
import sys
import time
import requests
import pandas as pd
import sqlite3
import json
import io
from datetime import datetime, timedelta
from pathlib import Path

print("🚀 Advanced Trading Bot - Starting...")
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
        "US30": {
            "name": "Dow Jones",
            "symbols": {
                "yahoo": "^DJI",
                "alpha_vantage": "DIA",
                "twelvedata": "DJI"
            },
            "csv_file": "US30_1H_MASTER.csv"
        },
        "XAUUSD": {
            "name": "Gold",
            "symbols": {
                "yahoo": "GC=F",
                "alpha_vantage": "GOLD",
                "twelvedata": "XAU/USD"
            },
            "csv_file": "XAUUSD_1h.csv"
        },
        "USDJPY": {
            "name": "USD/JPY",
            "symbols": {
                "yahoo": "JPY=X",
                "alpha_vantage": "USD/JPY",
                "twelvedata": "USD/JPY"
            },
            "csv_file": "USDJPY_1h.csv"
        }
    }
    
    DATA_SOURCES = ["csv", "twelvedata", "alpha_vantage", "yahoo"]
    
    # API Keys
    ALPHA_VANTAGE_KEY = os.getenv('ALPHA_VANTAGE_API_KEY', 'demo')
    TWELVE_DATA_KEY = os.getenv('TWELVE_DATA_API_KEY', 'demo')
    
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

# Advanced Data Fetcher with Multiple Sources
class AdvancedDataFetcher:
    def __init__(self):
        self.db = DatabaseManager()
        self.request_count = 0
        self.last_request_time = time.time()
    
    def _rate_limit(self):
        """Implement rate limiting for APIs"""
        elapsed = time.time() - self.last_request_time
        if elapsed < 12:  # Alpha Vantage: 5 calls/min (12s/call)
            time.sleep(12 - elapsed)
        
        self.request_count += 1
        self.last_request_time = time.time()
        
        if self.request_count % 5 == 0:  # Pause every 5 requests
            time.sleep(10)
    
    def fetch_data(self, symbol_config, lookback_days=30):
        symbol_name = symbol_config["name"]
        csv_file = symbol_config.get("csv_file")
        
        print(f"\n📊 Fetching {symbol_name}...")
        
        # Try all data sources in order of preference
        for source in Config.DATA_SOURCES:
            try:
                if source == "csv":
                    if not csv_file or not Path(csv_file).exists():
                        continue
                    
                    print(f"  Trying CSV file: {csv_file}")
                    df = self._fetch_csv_data(csv_file, lookback_days)
                    if df is not None:
                        self.db.save_ohlcv_data(symbol_name, df, "csv")
                        return df
                
                elif source == "twelvedata":
                    symbol = symbol_config["symbols"].get("twelvedata")
                    if not symbol:
                        continue
                    
                    print(f"  Trying Twelve Data: {symbol}")
                    self._rate_limit()
                    df = self._fetch_twelvedata_data(symbol, lookback_days)
                    if df is not None:
                        self.db.save_ohlcv_data(symbol_name, df, "twelvedata")
                        return df
                
                elif source == "alpha_vantage":
                    symbol = symbol_config["symbols"].get("alpha_vantage")
                    if not symbol:
                        continue
                    
                    print(f"  Trying Alpha Vantage: {symbol}")
                    self._rate_limit()
                    df = self._fetch_alpha_vantage_data(symbol, lookback_days)
                    if df is not None:
                        self.db.save_ohlcv_data(symbol_name, df, "alpha_vantage")
                        return df
                
                elif source == "yahoo":
                    symbol = symbol_config["symbols"].get("yahoo")
                    if not symbol:
                        continue
                    
                    print(f"  Trying Yahoo Finance: {symbol}")
                    df = self._fetch_yahoo_data(symbol, lookback_days)
                    if df is not None:
                        self.db.save_ohlcv_data(symbol_name, df, "yahoo")
                        return df
                        
            except Exception as e:
                print(f"  ❌ {source} failed: {e}")
                continue
        
        print(f"  ⚠️ All data sources failed for {symbol_name}")
        return None
    
    def _fetch_csv_data(self, csv_file, lookback_days):
        """Fetch data from CSV file"""
        try:
            df = pd.read_csv(csv_file)
            
            # Try to find date/time columns
            date_cols = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]
            if not date_cols:
                return None
                
            # Use the first date column found
            date_col = date_cols[0]
            df['timestamp'] = pd.to_datetime(df[date_col])
            df = df.set_index('timestamp')
            
            # Filter for the lookback period
            cutoff_date = datetime.now() - timedelta(days=lookback_days)
            df = df[df.index >= cutoff_date]
            
            # Standardize column names
            column_map = {
                'open': ['open', 'o'],
                'high': ['high', 'h'],
                'low': ['low', 'l'], 
                'close': ['close', 'c'],
                'volume': ['volume', 'v', 'vol']
            }
            
            for standard_name, possible_names in column_map.items():
                for name in possible_names:
                    if name in df.columns:
                        df[standard_name] = df[name]
                        break
            
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
            return df[['open', 'high', 'low', 'close', 'volume']]
            
        except Exception as e:
            print(f"  ❌ CSV load failed: {e}")
            return None
    
    def _fetch_twelvedata_data(self, symbol, lookback_days):
        """Fetch data from Twelve Data"""
        try:
            if Config.TWELVE_DATA_KEY == 'demo':
                print("  ⚠️ Using demo mode for Twelve Data")
                return None
                
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
            url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1h&start_date={start_date}&end_date={end_date}&apikey={Config.TWELVE_DATA_KEY}"
            
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                return None
                
            data = response.json()
            if 'values' not in data:
                return None
                
            df = pd.DataFrame(data['values'])
            if df.empty:
                return None
                
            df = df.rename(columns={'datetime': 'timestamp', 'open': 'open', 'high': 'high', 
                                  'low': 'low', 'close': 'close', 'volume': 'volume'})
            if 'volume' not in df.columns:
                df['volume'] = 0
                
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
            df = df.sort_index()
            df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
            
            print(f"  ✅ Loaded {len(df)} periods from Twelve Data")
            return df[['open', 'high', 'low', 'close', 'volume']]
        
        except Exception as e:
            print(f"  ❌ Twelve Data failed: {e}")
            return None
    
    def _fetch_alpha_vantage_data(self, symbol, lookback_days):
        """Fetch data from Alpha Vantage"""
        try:
            if Config.ALPHA_VANTAGE_KEY == 'demo':
                print("  ⚠️ Using demo mode for Alpha Vantage")
                return None
                
            url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval=60min&apikey={Config.ALPHA_VANTAGE_KEY}&outputsize=full&datatype=csv"
            
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                return None
                
            df = pd.read_csv(io.StringIO(response.text))
            if df.empty:
                return None
                
            df = df.rename(columns={'timestamp': 'timestamp', 'open': 'open', 'high': 'high', 
                                  'low': 'low', 'close': 'close', 'volume': 'volume'})
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
            df = df.sort_index()
            
            # Filter for the lookback period
            cutoff_date = datetime.now() - timedelta(days=lookback_days)
            df = df[df.index >= cutoff_date]
            
            print(f"  ✅ Loaded {len(df)} periods from Alpha Vantage")
            return df[['open', 'high', 'low', 'close', 'volume']]
        
        except Exception as e:
            print(f"  ❌ Alpha Vantage failed: {e}")
            return None
    
    def _fetch_yahoo_data(self, symbol, lookback_days):
        """Fetch data from Yahoo Finance"""
        try:
            import yfinance as yf
            
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=f"{lookback_days}d", interval="1h")
            
            if df is None or df.empty:
                return None
            
            df = df.reset_index()
            df = df.rename(columns={'Date': 'timestamp', 'Open': 'open', 'High': 'high', 
                                  'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
            
            print(f"  ✅ Loaded {len(df)} periods from Yahoo Finance")
            return df[['open', 'high', 'low', 'close', 'volume']]
        
        except Exception as e:
            print(f"  ❌ Yahoo Finance failed: {e}")
            return None

# Main Trading Bot
class TradingBot:
    def __init__(self):
        self.data_fetcher = AdvancedDataFetcher()
        print("✅ Trading bot initialized!")
    
    def backfill_data(self):
        print(f"\n📥 Backfilling {Config.LOOKBACK_DAYS} days of data...")
        for symbol, config in Config.TRADING_PAIRS.items():
            df = self.data_fetcher.fetch_data(config, Config.LOOKBACK_DAYS)
            time.sleep(2)  # Be gentle with API rate limits

# Command Line Interface
def show_help():
    print("\n🤖 AI Trading Bot - Command Help")
    print("=" * 40)
    print("python advanced_bot.py backfill - Backfill historical data")
    print("python advanced_bot.py help - Show this help")

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