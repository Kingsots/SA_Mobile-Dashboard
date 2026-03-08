"""
CSV Loader
Load historical data from CSV files across all timeframes.
"""

import pandas as pd
from pathlib import Path
from typing import Dict, Optional
from core.config import Config
from utils.logger import setup_logger

logger = setup_logger('CSVLoader')


class CSVLoader:
    """
    Load OHLCV data from CSV files.
    
    Expected CSV format:
    - Columns: timestamp/Date/Datetime, open/Open, high/High, low/Low, close/Close, volume/Volume
    - Index: timestamp (datetime)
    """
    
    def __init__(self, data_dir: Path = None):
        """
        Initialize CSV loader
        
        Args:
            data_dir: Directory containing CSV files (default: from config)
        """
        self.data_dir = data_dir or Config.DATA_DIR
        logger.info(f"CSV Loader initialized. Data directory: {self.data_dir}")
    
    def find_csv_file(self, symbol: str, timeframe: str) -> Optional[Path]:
        """
        Find CSV file for symbol and timeframe
        
        Expected filename patterns:
        - {SYMBOL}_{TIMEFRAME}.csv (e.g., US30_1h.csv, EURUSD_30m.csv)
        - {SYMBOL}_{TIMEFRAME}_MASTER.csv (e.g., US30_1H_MASTER.csv)
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe ('1d', '4h', '2h', '1h', '30m')
        
        Returns:
            Path to CSV file or None
        """
        # Convert timeframe to different formats
        tf_variants = {
            '1d': ['1d', '1D', 'daily', 'Daily', 'DAILY'],
            '4h': ['4h', '4H'],
            '2h': ['2h', '2H'],
            '1h': ['1h', '1H'],
            '30m': ['30m', '30M']
        }
        
        tf_options = tf_variants.get(timeframe, [timeframe])
        
        # Try different filename patterns
        for tf in tf_options:
            # Pattern 1: SYMBOL_TF.csv
            csv_file = self.data_dir / f"{symbol}_{tf}.csv"
            if csv_file.exists():
                return csv_file
            
            # Pattern 2: SYMBOL_TF_MASTER.csv
            csv_file = self.data_dir / f"{symbol}_{tf}_MASTER.csv"
            if csv_file.exists():
                return csv_file
            
            # Pattern 3: Check in timeframe subdirectory
            subdir = self.data_dir / tf
            if subdir.exists():
                csv_file = subdir / f"{symbol}.csv"
                if csv_file.exists():
                    return csv_file
        
        return None
    
    def load_csv(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Load CSV file for symbol and timeframe
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
        
        Returns:
            DataFrame with OHLCV data or None
        """
        csv_file = self.find_csv_file(symbol, timeframe)
        
        if csv_file is None:
            logger.warning(f"CSV file not found for {symbol} {timeframe}")
            return None
        
        try:
            logger.info(f"Loading {symbol} {timeframe} from {csv_file.name}")
            
            # Read CSV
            df = pd.read_csv(csv_file)
            
            # Standardize column names (handle different cases)
            column_mapping = {
                'Date': 'timestamp',
                'Datetime': 'timestamp',
                'DateTime': 'timestamp',
                'date': 'timestamp',
                'datetime': 'timestamp',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume',
                'OPEN': 'open',
                'HIGH': 'high',
                'LOW': 'low',
                'CLOSE': 'close',
                'VOLUME': 'volume'
            }
            
            df = df.rename(columns=column_mapping)
            
            # Ensure required columns exist
            required_cols = ['open', 'high', 'low', 'close']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                logger.error(f"Missing required columns in {csv_file.name}: {missing_cols}")
                return None
            
            # Handle timestamp column
            if 'timestamp' not in df.columns:
                # Try to use index as timestamp
                if df.index.name and 'date' in df.index.name.lower():
                    df['timestamp'] = df.index
                else:
                    logger.error(f"No timestamp column found in {csv_file.name}")
                    return None
            
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            
            # Remove rows with invalid timestamps
            df = df.dropna(subset=['timestamp'])
            
            # Set timestamp as index
            df = df.set_index('timestamp')
            
            # Sort by timestamp
            df = df.sort_index()
            
            # Add volume if missing
            if 'volume' not in df.columns:
                df['volume'] = 0
                logger.warning(f"Added zero volume column to {symbol} {timeframe}")
            
            # Keep only required columns
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            # Convert to numeric
            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Remove rows with NaN values
            df = df.dropna()
            
            logger.info(f"✅ Loaded {len(df)} records for {symbol} {timeframe}")
            
            return df
            
        except Exception as e:
            logger.error(f"Error loading CSV for {symbol} {timeframe}: {e}")
            return None
    
    def load_all_timeframes(self, symbol: str, timeframes: list = None) -> Dict[str, pd.DataFrame]:
        """
        Load all timeframes for a symbol
        
        Args:
            symbol: Trading symbol
            timeframes: List of timeframes (default: from config)
        
        Returns:
            Dict of {timeframe: DataFrame}
        """
        if timeframes is None:
            timeframes = Config.CASCADE_TIMEFRAMES
        
        result = {}
        
        for tf in timeframes:
            df = self.load_csv(symbol, tf)
            if df is not None:
                result[tf] = df
        
        logger.info(f"Loaded {len(result)}/{len(timeframes)} timeframes for {symbol}")
        
        return result
    
    def get_available_symbols(self) -> list:
        """
        Get list of symbols that have CSV data
        
        Returns:
            List of symbol names
        """
        if not self.data_dir.exists():
            return []
        
        symbols = set()
        
        # Scan for CSV files
        for csv_file in self.data_dir.glob("*.csv"):
            # Extract symbol from filename
            name = csv_file.stem
            
            # Remove timeframe suffix
            for tf in ['_1d', '_4h', '_2h', '_1h', '_30m', '_1H', '_4H', '_2H', '_30M']:
                if name.endswith(tf):
                    symbol = name[:-len(tf)]
                    symbols.add(symbol)
                    break
                if name.endswith(f"{tf}_MASTER"):
                    symbol = name[:-len(f"{tf}_MASTER")]
                    symbols.add(symbol)
                    break
        
        return sorted(list(symbols))
    
    def get_data_summary(self) -> Dict:
        """
        Get summary of available CSV data
        
        Returns:
            Dictionary with data summary
        """
        summary = {
            'data_dir': str(self.data_dir),
            'symbols': [],
            'timeframes_by_symbol': {}
        }
        
        symbols = self.get_available_symbols()
        summary['symbols'] = symbols
        
        for symbol in symbols:
            available_tfs = []
            for tf in Config.CASCADE_TIMEFRAMES:
                if self.find_csv_file(symbol, tf):
                    available_tfs.append(tf)
            
            summary['timeframes_by_symbol'][symbol] = available_tfs
        
        return summary
