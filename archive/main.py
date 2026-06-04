#!/usr/bin/env python3
"""
AI Trading Bot - Robust Data Collection Version
Multiple fallback sources with proper rate limiting for US30, forex pairs, and EURCHF
"""

import os
import sys
import time
import requests
import pandas as pd
import numpy as np
import sqlite3
import asyncio
import json
import io
from datetime import datetime, timedelta
from pathlib import Path
from telegram import Bot
from dotenv import load_dotenv
import yfinance as yf  # CSV download fallback

print("AI Trading Bot - Robust Data Collection")
print("=" * 50)

# =========================
# LOAD ENVIRONMENT
# =========================
def load_env():
    """Load environment variables from .env file"""
    env_path = Path('.env')
    if env_path.exists():
        print(f"Loading .env file from: {env_path.absolute()}")
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
                    print(f"  Set {key.strip()}")
    else:
        print(f"No .env file found at: {env_path.absolute()}")

load_env()

# =========================
# CONFIGURATION
# =========================
class Config:
    # Telegram credentials
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

    # Trading pairs with multiple symbol formats
    TRADING_PAIRS = {
        "USDJPY": {
            "name": "USD/JPY",
            "type": "forex",
            "symbols": {
                "yahoo": "JPY=X",
                "alpha_vantage": "USD/JPY",
                "twelvedata": "USD/JPY"
            }
        },
        "GBPUSD": {
            "name": "GBP/USD",
            "type": "forex",
            "symbols": {
                "yahoo": "GBPUSD=X",
                "alpha_vantage": "GBP/USD",
                "twelvedata": "GBP/USD"
            }
        },
        "EURUSD": {
            "name": "EUR/USD",
            "type": "forex",
            "symbols": {
                "yahoo": "EURUSD=X",
                "alpha_vantage": "EUR/USD",
                "twelvedata": "EUR/USD"
            }
        },
        "AUDUSD": {
            "name": "AUD/USD",
            "type": "forex",
            "symbols": {
                "yahoo": "AUDUSD=X",
                "alpha_vantage": "AUD/USD",
                "twelvedata": "AUD/USD"
            }
        },
        "AUDJPY": {
            "name": "AUD/JPY",
            "type": "forex",
            "symbols": {
                "yahoo": "AUDJPY=X",
                "alpha_vantage": "AUD/JPY",
                "twelvedata": "AUD/JPY"
            }
        },
        "GBPJPY": {
            "name": "GBP/JPY",
            "type": "forex",
            "symbols": {
                "yahoo": "GBPJPY=X",
                "alpha_vantage": "GBP/JPY",
                "twelvedata": "GBP/JPY"
            }
        },
        "CADJPY": {
            "name": "CAD/JPY",
            "type": "forex",
            "symbols": {
                "yahoo": "CADJPY=X",
                "alpha_vantage": "CAD/JPY",
                "twelvedata": "CAD/JPY"
            }
        },
        "EURJPY": {
            "name": "EUR/JPY",
            "type": "forex",
            "symbols": {
                "yahoo": "EURJPY=X",
                "alpha_vantage": "EUR/JPY",
                "twelvedata": "EUR/JPY"
            }
        },
        "EURGBP": {
            "name": "EUR/GBP",
            "type": "forex",
            "symbols": {
                "yahoo": "EURGBP=X",
                "alpha_vantage": "EUR/GBP",
                "twelvedata": "EUR/GBP"
            }
        },
        "USDCAD": {
            "name": "USD/CAD",
            "type": "forex",
            "symbols": {
                "yahoo": "USDCAD=X",
                "alpha_vantage": "USD/CAD",
                "twelvedata": "USD/CAD"
            }
        },
        "AUDCAD": {
            "name": "AUD/CAD",
            "type": "forex",
            "symbols": {
                "yahoo": "AUDCAD=X",
                "alpha_vantage": "AUD/CAD",
                "twelvedata": "AUD/CAD"
            }
        },
        "EURCHF": {
            "name": "EUR/CHF",
            "type": "forex",
            "symbols": {
                "yahoo": "EURCHF=X",
                "alpha_vantage": "EUR/CHF",
                "twelvedata": "EUR/CHF"
            }
        },
        "US30": {
            "name": "Dow Jones",
            "type": "index",
            "symbols": {
                "yahoo": "DIA",
                "alpha_vantage": "DIA",
                "twelvedata": "DJI"
            }
        },
        "NAS100": {
            "name": "Nasdaq 100",
            "type": "index",
            "symbols": {
                "yahoo": "QQQ",
                "alpha_vantage": "QQQ",
                "twelvedata": "NDX"
            }
        },
        "US500": {
            "name": "S&P 500",
            "type": "index",
            "symbols": {
                "yahoo": "SPY",
                "alpha_vantage": "SPY",
                "twelvedata": "SPX"
            }
        },
        "XAUUSD": {
            "name": "Gold",
            "type": "commodity",
            "symbols": {
                "yahoo": "GC=F",
                "alpha_vantage": "GOLD",
                "twelvedata": "XAU/USD"
            }
        }
    }

    # Data source priorities
    DATA_SOURCES = ["twelvedata", "alpha_vantage", "yahoo"]

    # API Keys
    ALPHA_VANTAGE_KEY = os.getenv('ALPHA_VANTAGE_API_KEY')
    TWELVE_DATA_KEY = os.getenv('TWELVE_DATA_API_KEY')

    # Analysis settings
    ANALYSIS_INTERVAL = 3600  # 1 hour
    LOOKBACK_DAYS = 60       # 60 days
    DATA_INTERVAL = "1h"     # 1-hour intervals

    # Database settings
    DB_PATH = "trading_bot.db"

    # Risk management
    MAX_RISK_PER_TRADE = 2   # 2% risk
    MIN_WIN_RATE = 60        # 60% win rate

# =========================
# DATABASE MANAGER
# =========================
class DatabaseManager:
    """Manage SQLite database for storing market data and signals"""
    
    def __init__(self, db_path=Config.DB_PATH):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ohlcv_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timestamp TEXT NOT NULL,
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
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS indicators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            rsi REAL,
            ema_12 REAL,
            ema_26 REAL,
            atr REAL,
            volatility REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, timestamp)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            confidence REAL,
            price REAL,
            indicators JSON,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        conn.close()
        print(f"Database initialized at {self.db_path}")
    
    def save_ohlcv_data(self, symbol, df, source):
        """Save OHLCV data to database"""
        if df is None or df.empty:
            print(f"No data to save for {symbol}")
            return
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        symbol_upper = symbol.upper()  # Ensure consistent symbol case
        saved_rows = 0
        for index, row in df.iterrows():
            try:
                timestamp_str = index.strftime('%Y-%m-%d %H:%M:%S') if hasattr(index, 'strftime') else str(index)
                raw_vol = row.get('volume', 0)
                safe_vol = int(float(raw_vol)) if pd.notna(raw_vol) else 0
                cursor.execute('''
                INSERT OR IGNORE INTO ohlcv_data 
                (symbol, timestamp, open, high, low, close, volume, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol_upper,
                    timestamp_str,
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    safe_vol,
                    source
                ))
                saved_rows += cursor.rowcount
            except Exception as e:
                print(f"Error saving {symbol_upper} data: {e}")
        
        conn.commit()
        conn.close()
        print(f"Saved {saved_rows} records for {symbol_upper} from {source}")
    
    def save_indicators(self, symbol, timestamp, indicators):
        """Save technical indicators to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S') if hasattr(timestamp, 'strftime') else str(timestamp)
            cursor.execute('''
            INSERT OR REPLACE INTO indicators 
            (symbol, timestamp, rsi, ema_12, ema_26, atr, volatility)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                symbol.upper(),
                timestamp_str,
                indicators.get('rsi'),
                indicators.get('ema_12'),
                indicators.get('ema_26'),
                indicators.get('atr'),
                indicators.get('volatility')
            ))
        except Exception as e:
            print(f"Error saving {symbol.upper()} indicators: {e}")
        
        conn.commit()
        conn.close()
    
    def save_signal(self, symbol, timestamp, signal_type, confidence, price, indicators):
        """Save trading signal to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S') if hasattr(timestamp, 'strftime') else str(timestamp)
            cursor.execute('''
            INSERT INTO signals 
            (symbol, timestamp, signal_type, confidence, price, indicators)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                symbol.upper(),
                timestamp_str,
                signal_type,
                confidence,
                price,
                json.dumps(indicators)
            ))
        except Exception as e:
            print(f"Error saving {symbol.upper()} signal: {e}")
        
        conn.commit()
        conn.close()
    
    def get_last_signal_time(self, symbol):
        """Get the timestamp of the last signal for a symbol"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT MAX(timestamp) FROM signals WHERE symbol = ?
        ''', (symbol.upper(),))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result and result[0] else None
    
    def should_send_signal(self, symbol, signal_type):
        """Enforce 4h44m cooldown for same-direction signals"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT timestamp, signal_type FROM signals
        WHERE symbol = ?
        ORDER BY timestamp DESC
        LIMIT 1
        ''', (symbol.upper(),))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return True
        
        last_time_str, last_signal = result
        last_time = pd.to_datetime(last_time_str)
        now = pd.Timestamp.now()
        hours = (now - last_time).total_seconds() / 3600.0
        
        if last_signal == signal_type and hours < 4.733:
            return False
        return True
    
    def check_db_contents(self):
        """Print symbol counts in ohlcv_data table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT symbol, COUNT(*) FROM ohlcv_data GROUP BY symbol')
        results = cursor.fetchall()
        conn.close()
        if not results:
            print("No data in ohlcv_data table")
        else:
            print("Database contents (symbol, count):")
            for symbol, count in results:
                print(f"{symbol}: {count}")

# =========================
# MARKET DATA FETCHER
# =========================
class RobustMarketDataFetcher:
    """Fetch market data with multiple fallback sources"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.request_count = 0
        self.last_request_time = time.time()
        print("Initializing robust market data fetcher...")
    
    def fetch_data(self, symbol_key, symbol_config, lookback_days=60, interval="1h"):
        """Try multiple data sources until successful"""
        for source in Config.DATA_SOURCES:
            try:
                self._rate_limit()
                
                source_symbol = symbol_config["symbols"].get(source)
                if not source_symbol:
                    continue
                
                print(f"  Trying {source} for {symbol_config['name']} ({source_symbol})...")
                
                if source == "yahoo":
                    data = self._fetch_yahoo_data(source_symbol, lookback_days, interval)
                elif source == "alpha_vantage":
                    data = self._fetch_alpha_vantage_data(source_symbol, lookback_days, interval)
                elif source == "twelvedata":
                    data = self._fetch_twelvedata_data(source_symbol, lookback_days, interval)
                else:
                    continue
                
                if data is not None and not data.empty:
                    last_candle_time = data.index[-1]
                    current_time = pd.Timestamp.now(tz=last_candle_time.tz) if hasattr(last_candle_time, 'tz') else pd.Timestamp.now()
                    hours_diff = (current_time - last_candle_time).total_seconds() / 3600
                    
                    if hours_diff > 2:
                        print(f"  Stale data from {source}. Last candle: {last_candle_time}")
                        continue
                    
                    print(f"  Success with {source}")
                    self.db.save_ohlcv_data(symbol_key, data, source)
                    return data
                
            except Exception as e:
                print(f"  {source} failed: {str(e)}")
                continue
        
        print(f"  All data sources failed for {symbol_config['name']}, trying CSV")
        try:
            csv_file = f"{symbol_key}_1h.csv"
            if symbol_key == "US30" and not Path(csv_file).exists():
                csv_file = "US30_1H_MASTER.csv"
            df = pd.read_csv(csv_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
            df = df[['open', 'high', 'low', 'close', 'volume']].tail(lookback_days * 24)
            print(f"  Loaded {len(df)} periods from {csv_file}")
            self.db.save_ohlcv_data(symbol_key, df, "csv")
            return df
        except FileNotFoundError:
            print(f"  CSV not found for {symbol_key}")
            return None
    
    def _rate_limit(self):
        """Implement rate limiting for APIs"""
        elapsed = time.time() - self.last_request_time
        if elapsed < 12:  # Alpha Vantage: 5 calls/min (12s/call)
            time.sleep(12 - elapsed)
        
        self.request_count += 1
        self.last_request_time = time.time()
        
        if self.request_count % 5 == 0:  # Pause every 5 requests
            time.sleep(10)
    
    def _fetch_yahoo_data(self, symbol, lookback_days, interval):
        """Fetch data from Yahoo Finance"""
        try:
            period = f"{lookback_days}d"
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval, auto_adjust=True)
            
            if df is None or df.empty:
                return None
            
            df = df.reset_index()
            df = df.rename(columns={'Date': 'timestamp', 'Open': 'open', 'High': 'high', 
                                  'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
            return df[['open', 'high', 'low', 'close', 'volume']]
        
        except Exception as e:
            print(f"Yahoo Finance error: {e}")
            return None
    
    def _fetch_alpha_vantage_data(self, symbol, lookback_days, interval):
        """Fetch data from Alpha Vantage"""
        try:
            if not Config.ALPHA_VANTAGE_KEY:
                return None
            interval_map = {"1h": "60min"}
            av_interval = interval_map.get(interval, "60min")
            url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval={av_interval}&apikey={Config.ALPHA_VANTAGE_KEY}&outputsize=full&datatype=csv"
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
            cutoff_date = datetime.now() - timedelta(days=lookback_days)
            df = df[df.index >= cutoff_date]
            return df[['open', 'high', 'low', 'close', 'volume']]
        
        except Exception as e:
            print(f"Alpha Vantage error: {e}")
            return None
    
    def _fetch_twelvedata_data(self, symbol, lookback_days, interval):
        """Fetch data from Twelve Data"""
        try:
            if not Config.TWELVE_DATA_KEY:
                return None
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
            url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&start_date={start_date}&end_date={end_date}&apikey={Config.TWELVE_DATA_KEY}"
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
            return df[['open', 'high', 'low', 'close', 'volume']]
        
        except Exception as e:
            print(f"Twelve Data error: {e}")
            return None

# =========================
# TECHNICAL ANALYSIS ENGINE
# =========================
class TechnicalAnalysis:
    """Advanced technical analysis with ATR and volatility"""
    
    def calculate_indicators(self, df):
        """Calculate all technical indicators"""
        if df is None or len(df) < 20:
            return None
        
        try:
            indicators = {}
            indicators['rsi'] = self.calculate_rsi(df['close'])
            indicators['ema_12'] = float(df['close'].ewm(span=12).mean().iloc[-1])
            indicators['ema_26'] = float(df['close'].ewm(span=26).mean().iloc[-1])
            indicators['atr'] = self.calculate_atr(df)
            returns = df['close'].pct_change().dropna()
            indicators['volatility'] = float(returns.std() * 100) if len(returns) > 0 else 1.0
            return indicators
        
        except Exception as e:
            print(f"Indicator calculation error: {str(e)}")
            return None
    
    def calculate_rsi(self, prices, period=14):
        """Calculate Relative Strength Index"""
        if len(prices) < period + 1:
            return 50.0
        try:
            delta = prices.diff()
            gain = delta.where(delta > 0, 0).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss.replace(0, np.nan)
            rsi = 100 - (100 / (1 + rs))
            result = float(rsi.iloc[-1])
            return result if not pd.isna(result) else 50.0
        except:
            return 50.0
    
    def calculate_atr(self, df, period=14):
        """Calculate Average True Range"""
        try:
            high = df['high']
            low = df['low']
            close = df['close']
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(period).mean()
            return float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0.0
        except:
            return 0.0

# =========================
# SIGNAL ENGINE
# =========================
class SignalEngine:
    """Rule-based signal generation with ML integration"""
    
    def _rsi_series(self, prices, period=14):
        """Calculate RSI series for slope features"""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(method='bfill').fillna(50.0)
    
    def generate_signal(self, df, indicators):
        """Generate trading signal based on ML or rule-based logic"""
        try:
            import pickle
            with open('trading_model.pkl', 'rb') as f:
                model = pickle.load(f)
            
            close = float(df['close'].iloc[-1])
            ema_alignment = float(indicators.get('ema_12', 0.0) - indicators.get('ema_26', 0.0))
            rsi_now = float(indicators.get('rsi', 50.0))
            
            rsi_series = self._rsi_series(df['close'])
            rsi_prev = float(rsi_series.iloc[-2]) if len(rsi_series) >= 2 else rsi_now
            rsi_slope = rsi_now - rsi_prev
            
            vol_roll = df['volume'].rolling(20)
            vol_mean = float(vol_roll.mean().iloc[-1]) if len(df) >= 20 else float(df['volume'].mean())
            vol_std = float(vol_roll.std(ddof=0).iloc[-1]) if len(df) >= 20 else float(df['volume'].std(ddof=0))
            volume_zscore = 0.0
            if np.isfinite(vol_std) and vol_std > 0:
                volume_zscore = (float(df['volume'].iloc[-1]) - vol_mean) / vol_std
            
            mom3 = float(df['close'].pct_change(3).iloc[-1]) if len(df) >= 4 else 0.0
            atr = float(indicators.get('atr', 0.0))
            atr_pct = (atr / close) if close > 0 else 0.0
            vol_frac = float(indicators.get('volatility', 0.0)) / 100.0
            
            features = np.array([[rsi_now, rsi_slope, ema_alignment, volume_zscore, mom3, atr_pct]], dtype=float)
            features[~np.isfinite(features)] = 0.0
            
            proba = model.predict_proba(features)[0][1] * 100.0
            confidence = float(np.clip(proba, 0.0, 100.0))
            
            if confidence > 60:
                return {"signal": "BUY", "confidence": confidence}
            elif confidence < 40:
                return {"signal": "SELL", "confidence": float(100.0 - confidence)}
            else:
                return {"signal": "HOLD", "confidence": 0.0}
        
        except Exception as e:
            print(f"ML signal error: {e}")
            try:
                close = df['close'].iloc[-1]
                prev_close = df['close'].iloc[-2]
                open_ = df['open'].iloc[-1]
                prev_open = df['open'].iloc[-2]
                
                bull, bear = 0.0, 0.0
                
                if indicators['ema_12'] > indicators['ema_26']:
                    bull += 1
                else:
                    bear += 1
                
                if indicators['rsi'] < 30:
                    bull += 1
                elif indicators['rsi'] > 70:
                    bear += 1
                elif 40 <= indicators['rsi'] <= 60:
                    if bull > bear:
                        bull += 0.5
                    else:
                        bear += 0.5
                
                is_bull_engulf = (close > open_ and prev_close < prev_open and open_ < prev_close and close > prev_open)
                is_bear_engulf = (close < open_ and prev_close > prev_open and open_ > prev_close and close < prev_open)
                
                if is_bull_engulf:
                    bull += 2
                elif is_bear_engulf:
                    bear += 2
                
                if indicators['volatility'] > 3.0:
                    bull *= 0.7
                    bear *= 0.7
                
                if bull > bear + 1:
                    return {"signal": "BUY", "confidence": float(min(95, bull * 20))}
                elif bear > bull + 1:
                    return {"signal": "SELL", "confidence": float(min(95, bear * 20))}
                else:
                    return {"signal": "HOLD", "confidence": 0.0}
            except Exception as e:
                print(f"Signal generation error: {e}")
                return {"signal": "HOLD", "confidence": 0.0}

# =========================
# TELEGRAM BOT
# =========================
class TelegramBot:
    """Telegram messaging for signals"""
    
    def __init__(self, token, chat_id):
        self.bot = Bot(token)
        self.chat_id = chat_id
    
    async def send_message(self, message):
        """Send message to Telegram with error handling"""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="Markdown"
            )
            print(f"  Telegram message sent successfully")
            return True
        except Exception as e:
            print(f"  Telegram error: {e}")
            return False
    
    async def send_signals_batch(self, signals):
        """Send signals in a single batch message to avoid rate limits"""
        if not signals:
            return
        text = "*Trading Signals Alert*\n\n"
        for sym, sig, price, ind in signals:
            text += f"• *{sym}*: {sig['signal']} ({sig['confidence']:.1f}%) @ {price:.5f}\n"
        await self.send_message(text.strip())
        await asyncio.sleep(2)  # Throttle to prevent timeouts

# =========================
# MAIN TRADING BOT
# =========================
class TradingBot:
    """Main trading bot orchestrator"""
    
    def __init__(self):
        self.data_fetcher = RobustMarketDataFetcher()
        self.technical_analyzer = TechnicalAnalysis()
        self.signal_engine = SignalEngine()
        self.db = DatabaseManager()
        if Config.TELEGRAM_TOKEN and Config.CHAT_ID:
            self.telegram_bot = TelegramBot(Config.TELEGRAM_TOKEN, Config.CHAT_ID)
        else:
            self.telegram_bot = None
            print("Telegram not configured - will run without notifications")
        print("Trading bot initialized!")
    
    async def backfill_data(self):
        """Backfill historical data for all symbols"""
        print(f"\nBackfilling {Config.LOOKBACK_DAYS} days of data...")
        print("=" * 50)
        
        for symbol, config in Config.TRADING_PAIRS.items():
            print(f"\nAnalyzing {symbol} ({config['name']})...")
            try:
                df = self.data_fetcher.fetch_data(symbol, config, Config.LOOKBACK_DAYS, Config.DATA_INTERVAL)
                if df is not None:
                    print(f"  Backfilled {len(df)} periods")
                else:
                    print(f"  Failed to backfill {symbol}")
                time.sleep(2)
            except Exception as e:
                print(f"  Error backfilling {symbol}: {str(e)}")
    
    async def run_scanner(self):
        """Run the market scanner for signals"""
        print(f"\nRunning Market Scanner at {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 60)
        
        new_signals = []
        for symbol, config in Config.TRADING_PAIRS.items():
            print(f"\nAnalyzing {symbol} ({config['name']})...")
            try:
                df = self.data_fetcher.fetch_data(symbol, config, 5, Config.DATA_INTERVAL)
                if df is None or len(df) < 20:
                    print(f"  Insufficient data for {symbol}")
                    continue
                
                indicators = self.technical_analyzer.calculate_indicators(df)
                if not indicators:
                    print(f"  Indicator calculation failed for {symbol}")
                    continue
                
                self.db.save_indicators(symbol, df.index[-1], indicators)
                
                signal_data = self.signal_engine.generate_signal(df, indicators)
                last_signal_time = self.db.get_last_signal_time(symbol)
                current_time = df.index[-1]
                
                is_new_signal = (
                    last_signal_time is None or 
                    pd.to_datetime(last_signal_time) < current_time or
                    signal_data['signal'] != 'HOLD'
                )
                
                if is_new_signal and signal_data['signal'] != 'HOLD':
                    if self.db.should_send_signal(symbol, signal_data['signal']):
                        self.db.save_signal(
                            symbol, 
                            current_time, 
                            signal_data['signal'], 
                            signal_data['confidence'],
                            df['close'].iloc[-1],
                            indicators
                        )
                        new_signals.append((symbol, signal_data, df['close'].iloc[-1], indicators))
                        print(f"  NEW SIGNAL: {symbol} - {signal_data['signal']} ({signal_data['confidence']:.1f}%)")
                    else:
                        print(f"  DUPLICATE SIGNAL SKIPPED: {symbol} - {signal_data['signal']} (within 4h44m cooldown)")
                else:
                    print(f"  {symbol}: {signal_data['signal']} ({signal_data['confidence']:.1f}%) - No change")
                
                time.sleep(1)
            
            except Exception as e:
                print(f"  Error processing {symbol}: {e}")
        
        if self.telegram_bot and new_signals:
            print(f"\nSending {len(new_signals)} new signals to Telegram...")
            await self.telegram_bot.send_signals_batch(new_signals)
        
        print(f"\nScanner Complete: {len(new_signals)} new signals found")
        return new_signals
    
    async def run_continuous(self):
        """Run the scanner continuously"""
        print("Starting continuous scanning...")
        print(f"Will run every {Config.ANALYSIS_INTERVAL//3600} hours")
        
        while True:
            await self.run_scanner()
            next_run = datetime.now() + timedelta(seconds=Config.ANALYSIS_INTERVAL)
            print(f"\nNext scan at: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            await asyncio.sleep(Config.ANALYSIS_INTERVAL)

# =========================
# COMMAND LINE INTERFACE
# =========================
def show_help():
    """Show available commands"""
    print("\nAI Trading Bot - Command Help")
    print("=" * 40)
    print("python main.py backfill - Backfill historical data")
    print("python main.py scan     - Run a single scan")
    print("python main.py monitor  - Run continuous monitoring")
    print("python main.py check_db - Check database contents")
    print("python main.py help     - Show this help")

async def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        show_help()
        return
    
    command = sys.argv[1].lower()
    bot = TradingBot()
    
    if command == "backfill":
        await bot.backfill_data()
    elif command == "scan":
        await bot.run_scanner()
    elif command == "monitor":
        await bot.run_continuous()
    elif command == "check_db":
        bot.db.check_db_contents()
    elif command == "help":
        show_help()
    else:
        print(f"Unknown command: {command}")
        show_help()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")