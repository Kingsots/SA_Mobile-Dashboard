"""
Feature Engineering Engine
Computes all indicators for ML pipeline: OBV, A/D, VWAP, plus existing EMA/RSI/volume
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Optional

from core.config import Config
from core.database import DatabaseManager
from core.indicators import TechnicalIndicators

# ==========================================
# FEATURE SETS (PREVENT LEAKAGE)
# ==========================================

# Price features (open/high/low/close) excluded from ML to prevent circular prediction
# VWAP excluded because it incorporates current bar close in calculation
# Only indicators and derivatives (slopes, ratios) are safe for prediction
ML_FEATURE_COLUMNS = [
    'ema_21', 'ema_100', 'rsi_14',
    'volume_sma_20', 'volume_ratio',
    'obv', 'ad', 'vwap_slope'  # vwap removed, only slope kept
]

# All features kept in database (OHLC needed for ATR calculations)
DATABASE_COLUMNS = [
    'open', 'high', 'low', 'close', 'volume',
    'ema_21', 'ema_100', 'rsi_14',
    'volume_sma_20', 'volume_ratio',
    'obv', 'ad', 'vwap', 'vwap_slope'
]

def compute_daily_ema(df, timestamp_col='timestamp', price_col='close', period=100):
    import pandas as pd
    temp = df.copy()
    temp[timestamp_col] = pd.to_datetime(temp[timestamp_col])
    temp = temp.set_index(timestamp_col)
    daily = temp[price_col].resample('D').last().dropna()
    daily_ema = daily.ewm(span=period, adjust=False).mean().rename('daily_ema')
    daily_ema_df = daily_ema.to_frame()
    daily_ema_df['date'] = daily_ema_df.index.date
    df['date'] = pd.to_datetime(df[timestamp_col]).dt.date
    df = df.merge(daily_ema_df[['daily_ema', 'date']], on='date', how='left')
    df = df.drop(columns=['date'])
    return df

class FeatureEngine:
    """
    Compute all features for ML model training and inference
    
    Features:
    - Existing: EMA 21/100, RSI 14, Volume SMA 20, Volume Ratio
    - New: OBV, A/D (Accumulation/Distribution), VWAP, VWAP Slope
    """
    
    def __init__(self):
        self.db = DatabaseManager()
    
    def compute_obv(self, df: pd.DataFrame) -> pd.Series:
        """
        Compute On-Balance Volume (OBV)
        
        OBV = cumsum(volume * sign(close - close.shift(1)))
        
        Args:
            df: DataFrame with 'close' and 'volume' columns
            
        Returns:
            Series with OBV values
        """
        if df is None or df.empty:
            return pd.Series()
        
        # Calculate price change direction
        price_change = df['close'].diff()
        direction = np.sign(price_change)
        
        # OBV = cumulative sum of (volume * direction)
        obv = (df['volume'] * direction).cumsum()
        
        return obv
    
    def compute_ad(self, df: pd.DataFrame) -> pd.Series:
        """
        Compute Accumulation/Distribution (A/D) Line
        
        CLV = ((close - low) - (high - close)) / (high - low)
        A/D = cumsum(CLV * volume)
        
        Args:
            df: DataFrame with OHLCV columns
            
        Returns:
            Series with A/D values
        """
        if df is None or df.empty:
            return pd.Series()
        
        # Calculate Close Location Value (CLV)
        # Avoid division by zero
        high_low_diff = df['high'] - df['low']
        high_low_diff = high_low_diff.replace(0, np.nan)
        
        clv = ((df['close'] - df['low']) - (df['high'] - df['close'])) / high_low_diff
        clv = clv.fillna(0)
        
        # A/D Line = cumulative sum of (CLV * volume)
        ad_line = (clv * df['volume']).cumsum()
        
        return ad_line
    
    def compute_vwap(self, df: pd.DataFrame) -> pd.Series:
        """
        Compute Volume Weighted Average Price (VWAP)
        
        Typical Price = (high + low + close) / 3
        VWAP = cumsum(typical_price * volume) / cumsum(volume)
        
        Args:
            df: DataFrame with OHLCV columns
            
        Returns:
            Series with VWAP values
        """
        if df is None or df.empty:
            return pd.Series()
        
        # Calculate typical price
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        
        # VWAP = cumulative (price * volume) / cumulative volume
        vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
        
        # Replace inf/-inf with NaN for safety
        vwap = vwap.replace([np.inf, -np.inf], np.nan)
        
        return vwap
    
    def compute_vwap_slope(self, df: pd.DataFrame, periods: int = 5) -> pd.Series:
        """
        Compute VWAP slope (rate of change)
        
        Slope = VWAP.diff(periods)
        
        Args:
            df: DataFrame with VWAP values
            periods: Number of periods for slope calculation
            
        Returns:
            Series with VWAP slope values
        """
        if df is None or df.empty or 'vwap' not in df.columns:
            return pd.Series()
        
        vwap_slope = df['vwap'].diff(periods)
        
        return vwap_slope
    
    def compute_volume_features(self, df: pd.DataFrame, period: int = 20) -> Dict[str, pd.Series]:
        """
        Compute volume-based features
        
        Args:
            df: DataFrame with 'volume' column
            period: SMA period
            
        Returns:
            Dict with volume_sma and volume_ratio
        """
        if df is None or df.empty:
            return {'volume_sma': pd.Series(), 'volume_ratio': pd.Series()}
        
        volume_sma = df['volume'].rolling(window=period).mean()
        volume_ratio = df['volume'] / volume_sma
        
        return {
            'volume_sma': volume_sma,
            'volume_ratio': volume_ratio
        }
    
    def compute_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute all features on a DataFrame
        
        Args:
            df: DataFrame with OHLCV data (index must be datetime)
            
        Returns:
            DataFrame with all features added
        """
        if df is None or df.empty:
            return df
        
        # Make a copy to avoid modifying original
        df = df.copy()

        # Ensure downstream indicators have explicit timestamp column
        if 'timestamp' not in df.columns:
            df['timestamp'] = df.index
        
        # ==========================================
        # EXISTING FEATURES
        # ==========================================
        
        # EMAs
        df['ema_21'] = df['close'].shift(1).ewm(span=Config.EMA_LTF, adjust=False).mean()
        df['ema_100'] = df['close'].shift(1).ewm(span=Config.EMA_HTF, adjust=False).mean()
        
        # RSI
        df['rsi_14'] = TechnicalIndicators.calculate_rsi(df['close'], Config.RSI_PERIOD)
        
        # Volume features (safe division)
        df['volume_sma_20'] = df['volume'].shift(1).rolling(window=Config.VOLUME_PERIOD, min_periods=1).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma_20'].replace(0, np.nan)
        df['volume_ratio'] = df['volume_ratio'].fillna(1.0)  # Default to 1.0 instead of 0
        
        # ==========================================
        # NEW FEATURES (ML Pipeline)
        # ==========================================
        
        # OBV
        df['obv'] = self.compute_obv(df)
        
        # A/D Line
        df['ad'] = self.compute_ad(df)
        
        # --- Patch 5: VWAP based ONLY on past bars ---
        typ_price = (df['high'] + df['low'] + df['close']) / 3
        vwap_num = ((typ_price * df['volume']).shift(1)).cumsum()
        vwap_den = (df['volume'].shift(1)).cumsum().replace(0, 1)
        df['vwap'] = vwap_num / vwap_den
        df = df.dropna(subset=['vwap'])
        df['vwap'] = df['vwap'].replace([np.inf, -np.inf], np.nan)
        
        # VWAP Slope (rate of change over 5 periods)
        df['vwap_slope'] = df['vwap'].pct_change(periods=5).fillna(0)
        
        df = compute_daily_ema(df)
        
        # Coerce all feature columns to numeric, replacing any non-numeric with NaN
        feature_cols = ['open', 'high', 'low', 'close', 'volume', 'ema_21', 'ema_100', 'rsi_14',
                        'obv', 'ad', 'vwap', 'vwap_slope', 'volume_sma_20', 'volume_ratio']
        for col in feature_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # ==========================================
        # LAG FEATURES BY 1 BAR (CRITICAL FOR ML)
        # ==========================================
        # Trading reality: At close of bar N, we only know bars 0 through N-1
        # We predict bar N+1 using only data from bar N-1 and earlier
        # Using bar N data to predict bar N+1 is lookahead bias
        
        for col in ML_FEATURE_COLUMNS:
            if col in df.columns:
                df[f'{col}_lag1'] = df[col].shift(1)
        
        # Drop rows with NaN from lagging (first row after lag)
        # This is safe because we still have plenty of training data
        df = df.dropna(subset=[f'{col}_lag1' for col in ML_FEATURE_COLUMNS])

        # Restore timestamp index for downstream consumers
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
        
        return df
    
    def generate_features_for_ticker(self, ticker: str, interval: str, days: int = 90) -> Optional[pd.DataFrame]:
        """
        Generate features for a specific ticker from raw data
        
        Args:
            ticker: Trading symbol
            interval: Timeframe
            days: Number of days to process
            
        Returns:
            DataFrame with all features
        """
        print(f"🔧 Generating features for {ticker} ({interval})...")
        
        # Load raw OHLCV data
        df = self.db.load_raw_ohlcv(ticker, interval, days)
        
        if df is None or df.empty:
            print(f"   ⚠️  No raw data available for {ticker} ({interval})")
            return None
        
        # Compute all features
        df_features = self.compute_all_features(df)
        
        # Drop rows only where OHLCV (required columns) are NaN, allow indicator NaN for warmup
        df_features = df_features.dropna(subset=['open', 'high', 'low', 'close', 'volume'])
        
        if df_features.empty:
            print(f"   ⚠️  No valid features after dropna for {ticker} ({interval})")
            return None
        
        print(f"   ✅ Computed {len(df_features)} feature rows")
        
        return df_features
    
    def save_features_to_db(self, ticker: str, interval: str, df_features: pd.DataFrame):
        """
        Save computed features to database
        
        Saves both original features (for indicators/ATR) and lagged features (for ML).
        
        Args:
            ticker: Trading symbol
            interval: Timeframe
            df_features: DataFrame with all features
        """
        if df_features is None or df_features.empty:
            return
        
        print(f"💾 Saving features for {ticker} ({interval})...")
        
        saved_count = 0
        
        for timestamp, row in df_features.iterrows():
            # Save all database features (OHLC + indicators)
            features = {
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['volume'],
                'ema_21': row['ema_21'],
                'ema_100': row['ema_100'],
                'rsi_14': row['rsi_14'],
                'obv': row['obv'],
                'ad': row['ad'],
                'vwap': row['vwap'],
                'vwap_slope': row['vwap_slope'],
                'volume_sma_20': row['volume_sma_20'],
                'volume_ratio': row['volume_ratio']
            }
            
            # Also save lagged features for ML if they exist
            for col in ML_FEATURE_COLUMNS:
                lagged_col = f'{col}_lag1'
                if lagged_col in row.index:
                    features[lagged_col] = row[lagged_col]
            
            self.db.save_features(
                ticker=ticker,
                timestamp=timestamp.isoformat(),
                interval=interval,
                features=features
            )
            saved_count += 1
        
        print(f"   ✅ Saved {saved_count} feature rows to database")
    
    def process_all_tickers(self, interval: str, symbols: Optional[list] = None) -> Dict[str, pd.DataFrame]:
        """
        Generate features for all tickers in watchlist
        
        Args:
            interval: Timeframe to process
            symbols: List of symbols (default: all watchlist)
            
        Returns:
            Dict mapping symbol -> features DataFrame
        """
        if symbols is None:
            symbols = Config.get_symbol_list()
        
        print(f"\n{'='*70}")
        print(f"  🔧 FEATURE ENGINEERING - {interval}")
        print(f"{'='*70}\n")
        
        results = {}
        
        for i, symbol in enumerate(symbols, 1):
            print(f"[{i}/{len(symbols)}] {symbol}")
            
            # Generate features
            df_features = self.generate_features_for_ticker(symbol, interval, days=90)
            
            if df_features is not None:
                # Save to database
                self.save_features_to_db(symbol, interval, df_features)
                results[symbol] = df_features
            
            print()
        
        print(f"✅ Feature generation complete: {len(results)}/{len(symbols)} symbols")
        
        return results


def main():
    """Test feature engine"""
    engine = FeatureEngine()
    
    # Test single ticker
    df = engine.generate_features_for_ticker('EURUSD', '1h', days=30)
    
    if df is not None:
        print(f"\n✅ Features computed for EURUSD:")
        print(df.tail())
        print(f"\nFeature columns: {list(df.columns)}")
        
        # Save to database
        engine.save_features_to_db('EURUSD', '1h', df)
    
    # Test batch processing
    results = engine.process_all_tickers('1h', symbols=['EURUSD', 'GBPUSD', 'USDJPY'])


if __name__ == '__main__':
    main()
