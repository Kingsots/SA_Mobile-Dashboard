"""
Configuration Settings for OptiCore Trading Bot
Matches Pine Script settings exactly: EMA 21/100, RSI 14, Daily HTF, Strict Engulfing
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """
    Central configuration matching your Pine Script strategy:
    - EMA 21 (Lower Timeframe)
    - EMA 100 (Daily Timeframe)
    - RSI 14
    - Strict Engulfing = True
    - Volume Filter = 1.2x
    """
    
    # ==========================================
    # PINE SCRIPT SETTINGS (OptiCore Strategy)
    # ==========================================
    
    # EMA Settings
    EMA_LTF = 21          # Lower timeframe EMA (changed from 44)
    EMA_HTF = 100         # Daily EMA for trend filter
    
    # RSI Settings
    RSI_PERIOD = 14
    RSI_LONG_THRESHOLD = 50   # RSI > 50 for longs
    RSI_SHORT_THRESHOLD = 50  # RSI < 50 for shorts
    
    # Volume Filter
    VOLUME_PERIOD = 20
    VOLUME_MULTIPLIER = 1.2   # Volume must be > 1.2x average
    
    # Engulfing Pattern
    STRICT_ENGULFING = True   # Require strict engulfing candles
    
    # ==========================================
    # TIMEFRAME SETTINGS
    # ==========================================
    
    # Entry timeframes to monitor (30m, 1h, and 4h)
    ENTRY_TIMEFRAMES = ['30m', '1h', '4h']  # Swing trader: 30m entry + 1h bridge + 4h confirmation
    
    # Multi-timeframe cascade for alignment checking
    # Daily → 4H → 2H → 1H → 30m (all must align)
    CASCADE_TIMEFRAMES = ['1d', '4h', '2h', '1h', '30m']
    
    # Interval scan schedule (minutes between sweeps)
    INTERVAL_SCAN_INTERVALS = {
        '30m': 30,   # 30m data updated every 30 minutes
        '1h': 60,    # 1h data updated every 60 minutes
        '4h': 240    # 4h data updated every 4 hours
    }
    
    # Higher timeframe for trend filter (Daily)
    HTF_TIMEFRAME = '1d'
    
    # ==========================================
    # WATCHLIST (Your Trading Pairs)
    # ==========================================
    
    WATCHLIST = {
        # Indices
        "NAS100": {
            "name": "NASDAQ 100",
            "type": "index",
            "yahoo_symbol": "^NDX",
            "enabled": False  # Tiingo intraday coverage unavailable; skip for now
        },
        "US30": {
            "name": "Dow Jones Industrial Average",
            "type": "index",
            "yahoo_symbol": "^DJI",
            "enabled": False
        },
        "US500": {
            "name": "S&P 500",
            "type": "index",
            "yahoo_symbol": "^GSPC",
            "enabled": False
        },
        
        # Commodities
        "XAUUSD": {
            "name": "Gold",
            "type": "commodity",
            "yahoo_symbol": "GC=F"
        },
        
        # Forex Majors
        "USDJPY": {
            "name": "USD/JPY",
            "type": "forex",
            "yahoo_symbol": "JPY=X"
        },
        "GBPUSD": {
            "name": "GBP/USD",
            "type": "forex",
            "yahoo_symbol": "GBPUSD=X"
        },
        "EURUSD": {
            "name": "EUR/USD",
            "type": "forex",
            "yahoo_symbol": "EURUSD=X"
        },
        "AUDUSD": {
            "name": "AUD/USD",
            "type": "forex",
            "yahoo_symbol": "AUDUSD=X"
        },
        "USDCAD": {
            "name": "USD/CAD",
            "type": "forex",
            "yahoo_symbol": "USDCAD=X"
        },
        
        # Forex Crosses
        "AUDJPY": {
            "name": "AUD/JPY",
            "type": "forex",
            "yahoo_symbol": "AUDJPY=X"
        },
        "GBPJPY": {
            "name": "GBP/JPY",
            "type": "forex",
            "yahoo_symbol": "GBPJPY=X"
        },
        "CADJPY": {
            "name": "CAD/JPY",
            "type": "forex",
            "yahoo_symbol": "CADJPY=X"
        },
        "EURJPY": {
            "name": "EUR/JPY",
            "type": "forex",
            "yahoo_symbol": "EURJPY=X"
        },
        "EURGBP": {
            "name": "EUR/GBP",
            "type": "forex",
            "yahoo_symbol": "EURGBP=X"
        },
        "AUDCAD": {
            "name": "AUD/CAD",
            "type": "forex",
            "yahoo_symbol": "AUDCAD=X"
        }
    }
    
    # ==========================================
    # DATABASE SETTINGS
    # ==========================================
    
    # Use absolute path to ensure correct database is accessed regardless of working directory
    DB_PATH = str(Path("/home/ubuntu/SilentAnalyst/trading_bot.db").expanduser())
    
    # Log directory for event debug logs and strategy signals
    LOG_DIR = "/home/ubuntu/SilentAnalyst/logs"
    
    # ==========================================
    # TELEGRAM SETTINGS
    # ==========================================
    
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    TELEGRAM_NOTIFICATIONS_ENABLED = True

    # Fine-grained Telegram toggles
    TELEGRAM_SEND_FETCH_REPORTS = False
    TELEGRAM_SEND_SIGNAL_ALERTS = True  # Send time-based fallback + event-driven alerts
    TELEGRAM_SEND_EVENT_ALERTS = True  # Send ONLY event-driven signal alerts
    TELEGRAM_SEND_EOD_REPORTS = False
    TELEGRAM_SEND_HEALTH_REPORTS = True
    # ==========================================
    # ALERT SETTINGS
    # ==========================================
    
    # Send both NEW and CONTINUATION signals
    ALERT_NEW_SIGNALS = True
    ALERT_CONTINUATION_SIGNALS = True
    
    # Minimum time between continuation alerts (seconds)
    CONTINUATION_ALERT_INTERVAL = 3600  # 1 hour
    
    # ==========================================
    # EVENT DETECTION THRESHOLDS (Forex optimized)
    # ==========================================
    
    # Breakout detection: Minimum % price movement to trigger event
    # Reduced from 0.15% to 0.05% for 1h forex candles
    EVENT_MIN_BREAKOUT_RATIO = 0.0005  # 0.05%
    
    # Minimum confidence for events to be considered valid
    EVENT_MIN_CONFIDENCE = 0.50  # 50% (relaxed from 0.55%)
    
    # Event cooldown: How long to suppress same event type on same symbol
    EVENT_COOLDOWN_SECONDS = 3600  # 1 hour per event type
    
    # ==========================================
    # MARKET HOURS CONFIGURATION
    # ==========================================
    # Forex market operates Sunday 22:00 UTC to Friday 22:00 UTC
    MARKET_OPEN_DAY = 6          # Sunday (0=Monday, 6=Sunday)
    MARKET_OPEN_HOUR = 22        # 22:00 UTC
    MARKET_CLOSE_DAY = 4         # Friday
    MARKET_CLOSE_HOUR = 22       # 22:00 UTC
    
    # ==========================================
    # DATA FRESHNESS CONFIGURATION
    # ==========================================
    # Maximum age for OHLCV data before skipping analysis (in minutes)
    # If latest candle is older than this, we skip event detection
    # 4 hours = 240 minutes (allows for one missed 4h candle)
    OHLCV_MAX_AGE_MINUTES = 240
    
    # Per-interval thresholds (optional - use OHLCV_MAX_AGE_MINUTES if not specified)
    OHLCV_MAX_AGE_BY_INTERVAL = {
        '30m': 60,   # 1 hour max age for 30m candles
        '1h': 90,    # 1.5 hours max age for 1h candles
        '4h': 300,   # 5 hours max age for 4h candles (allows 1 missed candle)
    }
    
    # ==========================================
    # ENGULFED STRUCTURE DETECTION (NEW)
    # ==========================================
    
    # Range identification lookback
    ENGULFED_RANGE_LOOKBACK = 20  # Candles to scan for range
    
    # Minimum pips for full body break
    ENGULFED_MIN_BREAK_PIPS = 2.0  # 2 pips minimum
    
    # Volume confirmation requirement
    ENGULFED_MIN_VOLUME_MULT = 1.2  # 1.2x average volume
    
    # Multi-timeframe filter (optional)
    ENGULFED_USE_DAILY_FILTER = False  # Set to True to require daily trend alignment
    
    # ==========================================
    # BACKTEST SETTINGS
    # ==========================================
    
    # Target performance metrics
    TARGET_EFFICIENCY = 0.65      # 65% win rate minimum
    TARGET_PROFIT_FACTOR = 1.5    # Profit factor minimum
    MAX_DRAWDOWN_THRESHOLD = 0.20 # 20% max drawdown
    
    # Backtesting period
    BACKTEST_DAYS = 90  # Test on 90 days of data
    
    # ==========================================
    # DATA SETTINGS
    # ==========================================
    
    # CSV file locations
    DATA_DIR = Path(__file__).parent.parent / "data_files"
    
    # Lookback period for data fetching
    LOOKBACK_DAYS = 60  # Fetch 60 days of historical data
    
    # API Keys (optional - for data fetching)
    ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY', '')
    TWELVE_DATA_API_KEY = os.getenv('TWELVE_DATA_API_KEY', '')
    
    # ==========================================
    # TIINGO API SETTINGS
    # ==========================================
    
    # Tiingo API Configuration
    TIINGO_API_TOKEN = os.getenv('TIINGO_API_TOKEN', 'e22a2ad1ff0cd51d1f174d04dd1e891dd0652694')
    TIINGO_BASE_URL = 'https://api.tiingo.com/tiingo/fx'
    
    # Tiingo Ticker Mapping (15 assets)
    TIINGO_TICKER_MAP = {
        # Indices (use IEX endpoint)
        "NAS100": "qqq",      # NASDAQ 100 ETF
        "US30": "dia",        # Dow Jones ETF
        "US500": "spy",       # S&P 500 ETF
        
        # Commodities
        "XAUUSD": "xauusd",   # Gold
        
        # Forex Majors
        "USDJPY": "usdjpy",
        "GBPUSD": "gbpusd",
        "EURUSD": "eurusd",
        "AUDUSD": "audusd",
        "USDCAD": "usdcad",
        
        # Forex Crosses
        "AUDJPY": "audjpy",
        "GBPJPY": "gbpjpy",
        "CADJPY": "cadjpy",
        "EURJPY": "eurjpy",
        "EURGBP": "eurgbp",
        "AUDCAD": "audcad"
    }
    
    # Rate Limits
    TIINGO_MAX_HOURLY_REQUESTS = 50
    TIINGO_MAX_DAILY_REQUESTS = 1000
    TIINGO_RATE_LIMIT_BUFFER = 5  # Keep 5 requests as buffer
    
    # Request Settings
    TIINGO_REQUEST_DELAY = 2.0    # Seconds between requests
    TIINGO_TIMEOUT = 20           # Request timeout in seconds (increased for API latency)
    TIINGO_MAX_RETRIES = 3        # Retry failed requests
    
    # ==========================================
    # ML PIPELINE SETTINGS
    # ==========================================
    
    # Feature Engineering
    FEATURE_WINDOW_SIZE = 90      # Days of historical data for features
    
    # XGBoost Model Parameters
    XGBOOST_N_ESTIMATORS = 200
    XGBOOST_MAX_DEPTH = 4
    XGBOOST_LEARNING_RATE = 0.05
    XGBOOST_MIN_CHILD_WEIGHT = 1
    XGBOOST_SUBSAMPLE = 0.8
    XGBOOST_COLSAMPLE_BYTREE = 0.8
    
    # Model Training
    ML_TRAIN_LOOKBACK_DAYS = 90
    ML_TEST_SPLIT = 0.2           # 80/20 train/test split
    ML_TARGET_ACCURACY = 0.45     # Minimum accuracy for deployment (forex volatility ~50%)
    
    # Model Versioning
    MODEL_DIR = Path(__file__).parent.parent / "data" / "models"
    MODEL_CURRENT_PATH = MODEL_DIR / "model_current.pkl"
    MODEL_METADATA_PATH = MODEL_DIR / "model_metadata.json"
    
    # Signal Generation
    ML_SIGNAL_CONFIDENCE_MIN = 0.33   # Minimum confidence to generate signal (lowered to 33% for observation phase)
    ML_SIGNAL_LABELS = {
        1: "BUY",
        -1: "SELL",
        0: "NEUTRAL"
    }
    FEATURE_REFRESH_LOOKBACK_DAYS = 90   # Days of raw data to use during refresh
    FEATURE_STALENESS_MINUTES = 90       # Trigger regeneration if features are older than this
    FEATURE_STALENESS_ALERT_MINUTES = 120  # Highlight in telemetry when features exceed this age
    
    # ==========================================
    # PIPELINE SETTINGS
    # ==========================================
    
    # Feature Toggle (backward compatibility)
    USE_TIINGO_PIPELINE = True   # Set to True to enable Tiingo + ML pipeline
    
    # Data Source Priority
    DATA_SOURCE_PRIORITY = ['tiingo', 'csv', 'yahoo']  # Try in this order
    
    # Data Retention
    DATA_RETENTION_DAYS = 90      # Keep 90 days of data
    CLEANUP_INTERVAL_HOURS = 24   # Run cleanup daily
    
    # Scan Intervals (for APScheduler)
    SCAN_INTERVALS = {
        '30min': 30,              # Every 30 minutes
        '1h': 60,                 # Every 60 minutes
        'EOD': '23:00'            # End of day at 23:00 UTC
    }
    
    # ==========================================
    # SCHEDULER SETTINGS
    # ==========================================
    
    EVENT_MODE_ENABLED = True
    ENABLE_TIME_TRIGGERED_SIGNALS = False  # Event-driven mode only
    
    # ==========================================
    # V2 EXECUTION ENGINE SETTINGS
    # ==========================================
    
    # Real-time entry/SL/TP calculation for V1 signals
    V2_EXECUTION_ENABLED = True  # If True, V2 enriches V1 signals with real-time prices
    V1_RETURN_ENTRY_PRICES = False  # If True, use old V1 calculation as fallback

    # Run bot at these intervals
    SCHEDULER_INTERVALS = {
        '30m': 30,  # Run every 30 minutes for 30m timeframe
        '1h': 60    # Run every 60 minutes for 1h timeframe
    }
    
    # ==========================================
    # LOGGING SETTINGS
    # ==========================================
    
    LOG_LEVEL = "INFO"
    LOG_FILE = "opticore_bot.log"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # ==========================================
    # DISPLAY SETTINGS
    # ==========================================
    
    # Show detailed signal information
    VERBOSE_ALERTS = True
    
    # Include cascade alignment in alerts
    SHOW_CASCADE_IN_ALERTS = True
    
    # Include backtest metrics in alerts
    SHOW_METRICS_IN_ALERTS = True
    
    
    @classmethod
    def get_symbol_list(cls):
        """Return list of symbol names"""
        return [symbol for symbol, meta in cls.WATCHLIST.items() if meta.get('enabled', True)]
    
    @classmethod
    def is_market_open(cls) -> bool:
        """
        Check if forex market is currently open.
        
        Forex trading hours: Sunday 22:00 UTC → Friday 22:00 UTC
        Market closed: Friday 22:00 UTC → Sunday 22:00 UTC (entire weekend)
        
        Returns:
            bool: True if market is open, False if closed
        """
        from datetime import datetime, timezone
        
        now = datetime.now(timezone.utc)
        day = now.weekday()  # 0=Monday, 4=Friday, 5=Saturday, 6=Sunday
        hour = now.hour
        
        # Saturday: Always closed
        if day == 5:
            return False
        
        # Sunday: Opens at 22:00 UTC
        if day == 6:
            return hour >= cls.MARKET_OPEN_HOUR
        
        # Friday: Closes at 22:00 UTC
        if day == 4:
            return hour < cls.MARKET_CLOSE_HOUR
        
        # Monday-Thursday: Always open
        return True
    
    @classmethod
    def get_next_market_open(cls):
        """
        Get the timestamp of the next market open.
        
        Returns:
            datetime: Next market open time (Sunday 22:00 UTC)
        """
        from datetime import datetime, timezone, timedelta
        
        now = datetime.now(timezone.utc)
        day = now.weekday()
        
        # If Saturday
        if day == 5:
            # Next open: Sunday at 22:00
            days_until_sunday = 1
            next_open = (now + timedelta(days=days_until_sunday)).replace(
                hour=cls.MARKET_OPEN_HOUR, minute=0, second=0, microsecond=0
            )
            return next_open
        
        # If Sunday before 22:00
        if day == 6 and now.hour < cls.MARKET_OPEN_HOUR:
            # Opens today at 22:00
            return now.replace(hour=cls.MARKET_OPEN_HOUR, minute=0, second=0, microsecond=0)
        
        # If Friday after 22:00
        if day == 4 and now.hour >= cls.MARKET_CLOSE_HOUR:
            # Next open: Sunday at 22:00 (2 days later)
            next_open = (now + timedelta(days=2)).replace(
                hour=cls.MARKET_OPEN_HOUR, minute=0, second=0, microsecond=0
            )
            return next_open
        
        # Market already open
        return now
    
    @classmethod
    def get_symbol_list(cls):
        """Return list of symbol names"""
        return [symbol for symbol, meta in cls.WATCHLIST.items() if meta.get('enabled', True)]
    
    @classmethod
    def get_yahoo_symbol(cls, symbol):
        """Get Yahoo Finance symbol for a given symbol"""
        return cls.WATCHLIST.get(symbol, {}).get('yahoo_symbol', symbol)
    
    @classmethod
    def get_tiingo_ticker(cls, symbol):
        """Get Tiingo ticker for a given symbol"""
        return cls.TIINGO_TICKER_MAP.get(symbol, symbol.lower())
    
    @classmethod
    def validate_config(cls):
        """Validate configuration settings"""
        errors = []
        
        # Check Telegram credentials
        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN not set in .env file")
        if not cls.TELEGRAM_CHAT_ID:
            errors.append("TELEGRAM_CHAT_ID not set in .env file")
        
        # Check data directory exists
        if not cls.DATA_DIR.exists():
            errors.append(f"Data directory not found: {cls.DATA_DIR}")
        
        if errors:
            return False, errors
        
        return True, []
    
    @classmethod
    def print_config(cls):
        """Print current configuration for debugging"""
        print("=" * 60)
        print("OptiCore Trading Bot Configuration")
        print("=" * 60)
        print(f"EMA Settings: LTF={cls.EMA_LTF}, HTF={cls.EMA_HTF}")
        print(f"RSI Period: {cls.RSI_PERIOD}")
        print(f"Volume Filter: {cls.VOLUME_MULTIPLIER}x average")
        print(f"Strict Engulfing: {cls.STRICT_ENGULFING}")
        print(f"Entry Timeframes: {', '.join(cls.ENTRY_TIMEFRAMES)}")
        print(f"HTF Filter: {cls.HTF_TIMEFRAME}")
        print(f"Watchlist: {len(cls.WATCHLIST)} symbols")
        print(f"Target Efficiency: {cls.TARGET_EFFICIENCY * 100}%")
        print("=" * 60)
