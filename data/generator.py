"""
Data Generator
Generate missing timeframe data (primarily 30-minute data).
"""

import pandas as pd
from pathlib import Path
from typing import Optional
from datetime import datetime
from core.config import Config
from utils.logger import setup_logger

logger = setup_logger('DataGenerator')


class DataGenerator:
    """
    Generate missing timeframe data:
    - Resample existing data to create 30m from 1h
    - Fetch fresh data from APIs for missing timeframes
    """
    
    @staticmethod
    def resample_to_30m(df_1h: pd.DataFrame) -> pd.DataFrame:
        """
        Resample 1-hour data to 30-minute intervals
        
        Note: This splits each 1h candle into two 30m candles (approximation)
        For real trading, it's better to fetch actual 30m data from API
        
        Args:
            df_1h: 1-hour DataFrame
        
        Returns:
            30-minute DataFrame (approximated)
        """
        if df_1h is None or df_1h.empty:
            return None
        
        logger.info("Resampling 1h data to 30m (approximation)")
        
        try:
            # Create 30m timeframe by duplicating each 1h candle
            records = []
            
            for timestamp, row in df_1h.iterrows():
                # First 30m candle of the hour
                records.append({
                    'timestamp': timestamp,
                    'open': row['open'],
                    'high': row['high'],
                    'low': (row['low'] + row['close']) / 2,  # Approximate
                    'close': (row['open'] + row['close']) / 2,  # Approximate
                    'volume': row['volume'] / 2
                })
                
                # Second 30m candle of the hour
                records.append({
                    'timestamp': timestamp + pd.Timedelta(minutes=30),
                    'open': (row['open'] + row['close']) / 2,  # Approximate
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'volume': row['volume'] / 2
                })
            
            df_30m = pd.DataFrame(records)
            df_30m = df_30m.set_index('timestamp')
            df_30m = df_30m.sort_index()
            
            logger.warning("⚠️ 30m data is approximated from 1h. Fetch real 30m data for accurate signals.")
            logger.info(f"✅ Generated {len(df_30m)} 30m records from {len(df_1h)} 1h records")
            
            return df_30m
            
        except Exception as e:
            logger.error(f"Error resampling to 30m: {e}")
            return None
    
    @staticmethod
    def fetch_30m_from_yahoo(symbol: str, lookback_days: int = 60) -> Optional[pd.DataFrame]:
        """
        Fetch actual 30-minute data from Yahoo Finance
        
        Args:
            symbol: Trading symbol
            lookback_days: Days of historical data
        
        Returns:
            30-minute DataFrame or None
        """
        try:
            import yfinance as yf
            
            yahoo_symbol = Config.get_yahoo_symbol(symbol)
            
            logger.info(f"Fetching 30m data from Yahoo for {symbol} ({yahoo_symbol})")
            
            ticker = yf.Ticker(yahoo_symbol)
            
            # Yahoo Finance supports 30m data for up to 60 days
            if lookback_days > 60:
                logger.warning(f"Yahoo Finance 30m data limited to 60 days. Using {lookback_days} may fail.")
            
            df = ticker.history(period=f"{lookback_days}d", interval="30m")
            
            if df is None or df.empty:
                logger.warning(f"No 30m data from Yahoo for {symbol}")
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
            
            logger.info(f"✅ Fetched {len(df)} 30m records from Yahoo for {symbol}")
            
            return df
            
        except ImportError:
            logger.error("yfinance not installed. Install with: pip install yfinance")
            return None
        except Exception as e:
            logger.error(f"Error fetching 30m data from Yahoo for {symbol}: {e}")
            return None
    
    @staticmethod
    def generate_30m_data(symbol: str, df_1h: pd.DataFrame = None) -> Optional[pd.DataFrame]:
        """
        Generate 30-minute data using best available method
        
        Priority:
        1. Fetch actual 30m data from Yahoo Finance
        2. Resample 1h data to 30m (approximation)
        
        Args:
            symbol: Trading symbol
            df_1h: 1-hour DataFrame (optional, for resampling fallback)
        
        Returns:
            30-minute DataFrame or None
        """
        # Priority 1: Try to fetch actual 30m data
        df_30m = DataGenerator.fetch_30m_from_yahoo(symbol)
        
        if df_30m is not None:
            return df_30m
        
        # Priority 2: Resample from 1h if available
        if df_1h is not None:
            logger.info(f"Falling back to resampling 1h → 30m for {symbol}")
            return DataGenerator.resample_to_30m(df_1h)
        
        logger.error(f"❌ Could not generate 30m data for {symbol}")
        return None
    
    @staticmethod
    def save_30m_to_csv(symbol: str, df_30m: pd.DataFrame, data_dir: Path = None):
        """
        Save 30-minute data to CSV file
        
        Args:
            symbol: Trading symbol
            df_30m: 30-minute DataFrame
            data_dir: Directory to save CSV (default: from config)
        """
        if data_dir is None:
            data_dir = Config.DATA_DIR
        
        if not data_dir.exists():
            data_dir.mkdir(parents=True, exist_ok=True)
        
        csv_file = data_dir / f"{symbol}_30m.csv"
        
        try:
            # Reset index to save timestamp as column
            df_save = df_30m.reset_index()
            df_save.to_csv(csv_file, index=False)
            
            logger.info(f"✅ Saved 30m data to {csv_file}")
            
        except Exception as e:
            logger.error(f"Error saving 30m CSV for {symbol}: {e}")
    
    @staticmethod
    def generate_all_30m_data(watchlist: list = None, save_csv: bool = True):
        """
        Generate 30-minute data for all symbols in watchlist
        
        Args:
            watchlist: List of symbols (default: from config)
            save_csv: Save generated data to CSV files
        """
        if watchlist is None:
            watchlist = Config.get_symbol_list()
        
        logger.info(f"Generating 30m data for {len(watchlist)} symbols")
        
        success_count = 0
        fail_count = 0
        
        for symbol in watchlist:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing {symbol}")
            logger.info(f"{'='*60}")
            
            # Try to fetch actual 30m data first
            df_30m = DataGenerator.fetch_30m_from_yahoo(symbol, lookback_days=60)
            
            if df_30m is not None:
                success_count += 1
                
                if save_csv:
                    DataGenerator.save_30m_to_csv(symbol, df_30m)
            else:
                fail_count += 1
                logger.warning(f"⚠️ Failed to generate 30m data for {symbol}")
        
        logger.info(f"\n{'='*60}")
        logger.info(f"30m Data Generation Complete")
        logger.info(f"{'='*60}")
        logger.info(f"Success: {success_count}/{len(watchlist)}")
        logger.info(f"Failed: {fail_count}/{len(watchlist)}")
        
        return success_count, fail_count
