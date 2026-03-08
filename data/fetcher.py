"""
Data Fetcher
Multi-source data fetching with CSV priority and API fallback.
"""

import pandas as pd
from typing import Dict, Optional
from datetime import datetime, timedelta
from core.config import Config
from core.database import DatabaseManager
from .csv_loader import CSVLoader
from utils.logger import setup_logger

logger = setup_logger('DataFetcher')


class DataFetcher:
    """
    Fetch OHLCV data from multiple sources with priority order:
    1. CSV files (if available)
    2. Database cache (if recent)
    3. Yahoo Finance API (fallback)
    4. Other APIs (if configured)
    """
    
    def __init__(self):
        """Initialize data fetcher"""
        self.csv_loader = CSVLoader()
        self.db = DatabaseManager()
        logger.info("Data Fetcher initialized")
    
    def fetch_from_csv(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Fetch data from CSV file
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
        
        Returns:
            DataFrame or None
        """
        return self.csv_loader.load_csv(symbol, timeframe)
    
    def fetch_from_database(self, symbol: str, timeframe: str, max_age_hours: int = 24) -> Optional[pd.DataFrame]:
        """
        Fetch recent data from database cache
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            max_age_hours: Maximum age of cached data in hours
        
        Returns:
            DataFrame or None
        """
        df = self.db.load_ohlcv_data(symbol, timeframe)
        
        if df is None or df.empty:
            return None
        
        # Check if data is recent enough
        last_timestamp = df.index[-1]
        age = datetime.now() - last_timestamp
        
        if age > timedelta(hours=max_age_hours):
            logger.info(f"Database data for {symbol} {timeframe} is too old ({age.total_seconds()/3600:.1f}h)")
            return None
        
        logger.info(f"✅ Loaded {len(df)} records from database for {symbol} {timeframe}")
        return df
    
    def fetch_from_yahoo(self, symbol: str, timeframe: str, lookback_days: int = None) -> Optional[pd.DataFrame]:
        """
        Fetch data from Yahoo Finance
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            lookback_days: Days of historical data
        
        Returns:
            DataFrame or None
        """
        if lookback_days is None:
            lookback_days = Config.LOOKBACK_DAYS
        
        try:
            import yfinance as yf
            
            # Get Yahoo symbol
            yahoo_symbol = Config.get_yahoo_symbol(symbol)
            
            # Map timeframe to Yahoo interval
            interval_map = {
                '30m': '30m',
                '1h': '1h',
                '2h': '2h',
                '4h': '4h',
                '1d': '1d'
            }
            
            interval = interval_map.get(timeframe, '1h')
            
            logger.info(f"Fetching {symbol} ({yahoo_symbol}) {timeframe} from Yahoo Finance...")
            
            ticker = yf.Ticker(yahoo_symbol)
            df = ticker.history(period=f"{lookback_days}d", interval=interval)
            
            if df is None or df.empty:
                logger.warning(f"No data from Yahoo for {symbol} {timeframe}")
                return None
            
            # Standardize DataFrame
            df = df.reset_index()
            df = df.rename(columns={
                'Date': 'timestamp',
                'Datetime': 'timestamp',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            logger.info(f"✅ Fetched {len(df)} records from Yahoo for {symbol} {timeframe}")
            
            # Save to database
            self.db.save_ohlcv_data(symbol, timeframe, df, 'yahoo')
            
            return df
            
        except ImportError:
            logger.error("yfinance not installed. Install with: pip install yfinance")
            return None
        except Exception as e:
            logger.error(f"Yahoo Finance fetch error for {symbol} {timeframe}: {e}")
            return None
    
    def fetch_data(self, symbol: str, timeframe: str, force_refresh: bool = False) -> Optional[pd.DataFrame]:
        """
        Fetch data with priority: CSV -> Database -> Yahoo Finance
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            force_refresh: Force fetch from API (skip CSV/DB)
        
        Returns:
            DataFrame or None
        """
        logger.info(f"Fetching data for {symbol} {timeframe}")
        
        if not force_refresh:
            # Priority 1: CSV files
            df = self.fetch_from_csv(symbol, timeframe)
            if df is not None:
                logger.info(f"✅ Using CSV data for {symbol} {timeframe}")
                # Also save to database for caching
                self.db.save_ohlcv_data(symbol, timeframe, df, 'csv')
                return df
            
            # Priority 2: Database cache
            df = self.fetch_from_database(symbol, timeframe, max_age_hours=24)
            if df is not None:
                logger.info(f"✅ Using database cache for {symbol} {timeframe}")
                return df
        
        # Priority 3: Yahoo Finance API
        df = self.fetch_from_yahoo(symbol, timeframe)
        if df is not None:
            logger.info(f"✅ Using Yahoo Finance data for {symbol} {timeframe}")
            return df
        
        logger.warning(f"❌ Could not fetch data for {symbol} {timeframe}")
        return None
    
    def fetch_all_timeframes(self, symbol: str, timeframes: list = None, 
                            force_refresh: bool = False) -> Dict[str, pd.DataFrame]:
        """
        Fetch all timeframes for a symbol
        
        Args:
            symbol: Trading symbol
            timeframes: List of timeframes (default: from config)
            force_refresh: Force fetch from API
        
        Returns:
            Dict of {timeframe: DataFrame}
        """
        if timeframes is None:
            timeframes = Config.CASCADE_TIMEFRAMES
        
        result = {}
        
        for tf in timeframes:
            df = self.fetch_data(symbol, tf, force_refresh)
            if df is not None:
                result[tf] = df
        
        logger.info(f"Fetched {len(result)}/{len(timeframes)} timeframes for {symbol}")
        
        return result
    
    def fetch_watchlist(self, timeframe: str, force_refresh: bool = False) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for all symbols in watchlist
        
        Args:
            timeframe: Timeframe to fetch
            force_refresh: Force fetch from API
        
        Returns:
            Dict of {symbol: DataFrame}
        """
        result = {}
        
        symbols = Config.get_symbol_list()
        logger.info(f"Fetching {timeframe} data for {len(symbols)} symbols")
        
        for symbol in symbols:
            df = self.fetch_data(symbol, timeframe, force_refresh)
            if df is not None:
                result[symbol] = df
        
        logger.info(f"Fetched data for {len(result)}/{len(symbols)} symbols")
        
        return result
    
    def get_data_status(self) -> Dict:
        """
        Get status of available data
        
        Returns:
            Dict with data availability status
        """
        status = {
            'csv_summary': self.csv_loader.get_data_summary(),
            'database_stats': self.db.get_database_stats(),
            'watchlist_symbols': Config.get_symbol_list(),
            'configured_timeframes': Config.CASCADE_TIMEFRAMES
        }
        
        return status
