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


class FeatureEngine:
    """
    Compute all features for ML model training and inference
    
    Features:
    - Existing: EMA 21/100, RSI 14, Volume SMA 20, Volume Ratio
    - New: OBV, A/D (Accumulation/Distribution), VWAP, VWAP Slope
    """
    
    def __init__(self):
        self.db = DatabaseManager()
    
    def _calculate_rsi_series(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate RSI as a pandas Series for vectorized operations
        
        Args:
            prices: Series of closing prices
            period: RSI period (default: 14)
            
        Returns:
            Series with RSI values
        """
        delta = prices.diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta.where(delta < 0, 0))
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.fillna(50.0)  # Fill NaN with neutral value
    
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
        
        For instruments with zero volume (forex), returns typical price instead.
        
        Args:
            df: DataFrame with OHLCV columns
            
        Returns:
            Series with VWAP values
        """
        if df is None or df.empty:
            return pd.Series()
        
        # Calculate typical price
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        
        # Check if volume data exists
        if df['volume'].sum() == 0:
            # For forex (no volume), use typical price as proxy
            return typical_price
        
        # VWAP = cumulative (price * volume) / cumulative volume
        cum_volume = df['volume'].cumsum()
        cum_volume = cum_volume.replace(0, np.nan)  # Avoid division by zero
        vwap = (typical_price * df['volume']).cumsum() / cum_volume
        vwap = vwap.fillna(typical_price)  # Fill NaN with typical price
        
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
    
    def compute_atr_series(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Compute Average True Range (ATR) as a Series
        
        Used by Context Engine for compression/expansion analysis.
        
        Args:
            df: DataFrame with 'high', 'low', 'close' columns
            period: ATR period (default: 14)
        
        Returns:
            Series with ATR values
        """
        if df is None or df.empty:
            return pd.Series()
        
        try:
            high = df['high']
            low = df['low']
            close = df['close']
            
            # Calculate True Range components
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            
            # True Range is the maximum of the three
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            # ATR is the moving average of True Range
            atr = tr.rolling(window=period).mean()
            
            return atr.fillna(0.0)
            
        except Exception as e:
            print(f"ATR series calculation error: {e}")
            return pd.Series(0.0, index=df.index)
    
    def compute_volume_features(self, df: pd.DataFrame, period: int = 20) -> Dict[str, pd.Series]:
        """
        Compute volume-based features
        
        For instruments with zero volume (forex), returns normalized placeholder values.
        
        Args:
            df: DataFrame with 'volume' column
            period: SMA period
            
        Returns:
            Dict with volume_sma and volume_ratio
        """
        if df is None or df.empty:
            return {'volume_sma': pd.Series(), 'volume_ratio': pd.Series()}
        
        # Check if volume data exists
        if df['volume'].sum() == 0:
            # For forex (no volume), return placeholder values
            return {
                'volume_sma': pd.Series([1.0] * len(df), index=df.index),
                'volume_ratio': pd.Series([1.0] * len(df), index=df.index)
            }
        
        volume_sma = df['volume'].rolling(window=period).mean()
        # Avoid division by zero
        volume_sma_safe = volume_sma.replace(0, np.nan)
        volume_ratio = df['volume'] / volume_sma_safe
        volume_ratio = volume_ratio.fillna(1.0)  # Fill NaN with neutral value
        
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
            DataFrame with all features added (all numeric types, no NaN in critical columns)
        """
        if df is None or df.empty:
            return df
        
        # Make a copy to avoid modifying original
        df = df.copy()
        
        # ==========================================
        # EXISTING FEATURES
        # ==========================================
        
        # EMAs
        df['ema_21'] = df['close'].ewm(span=Config.EMA_LTF, adjust=False).mean()
        df['ema_100'] = df['close'].ewm(span=Config.EMA_HTF, adjust=False).mean()
        
        # RSI
        df['rsi_14'] = self._calculate_rsi_series(df['close'], Config.RSI_PERIOD)
        
        # Volume features
        volume_features = self.compute_volume_features(df, Config.VOLUME_PERIOD)
        df['volume_sma_20'] = volume_features['volume_sma']
        df['volume_ratio'] = volume_features['volume_ratio']
        
        # ==========================================
        # NEW FEATURES (ML Pipeline)
        # ==========================================
        
        # OBV
        df['obv'] = self.compute_obv(df)
        
        # A/D Line
        df['ad'] = self.compute_ad(df)
        
        # VWAP
        df['vwap'] = self.compute_vwap(df)
        
        # VWAP Slope
        df['vwap_slope'] = self.compute_vwap_slope(df, periods=5)
        
        # ATR for Context Engine (compression/expansion analysis)
        df['atr_14'] = self.compute_atr_series(df, period=14)
        df['atr_sma_20'] = df['atr_14'].rolling(window=20).mean()
        
        # ==========================================
        # NUMERIC COERCION - Ensure all features are float64
        # ==========================================
        feature_cols = [
            'ema_21', 'ema_100', 'rsi_14', 'obv', 'ad', 'vwap', 
            'vwap_slope', 'volume_sma_20', 'volume_ratio', 'atr_14', 'atr_sma_20'
        ]
        
        for col in feature_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').astype(np.float64)
        
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
        
        # Drop rows with NaN (from indicators needing warmup)
        df_features = df_features.dropna()
        
        if df_features.empty:
            print(f"   ⚠️  No valid features after dropna for {ticker} ({interval})")
            return None
        
        print(f"   ✅ Computed {len(df_features)} feature rows")
        
        return df_features
    
    def save_features_to_db(self, ticker: str, interval: str, df_features: pd.DataFrame):
        """
        Save computed features to database
        
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
