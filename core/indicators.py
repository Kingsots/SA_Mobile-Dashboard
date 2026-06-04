"""
Technical Indicators Module
Implements all technical analysis calculations matching Pine Script logic.
"""

import pandas as pd
import numpy as np
from typing import Union, Tuple


class TechnicalIndicators:
    """
    Technical analysis indicators for OptiCore strategy.
    All calculations match Pine Script ta.* functions.
    """
    
    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
        """
        Calculate Relative Strength Index (RSI)
        
        Pine Script equivalent: ta.rsi(close, rsiLength)
        
        Args:
            prices: Series of closing prices
            period: RSI period (default: 14)
        
        Returns:
            RSI value (0-100)
        """
        if len(prices) < period + 1:
            return 50.0  # Neutral if not enough data
        
        try:
            # Calculate price changes
            delta = prices.diff()
            
            # Separate gains and losses
            gain = delta.where(delta > 0, 0)
            loss = (-delta.where(delta < 0, 0))
            
            # Calculate average gain and loss
            avg_gain = gain.rolling(window=period).mean()
            avg_loss = loss.rolling(window=period).mean()
            
            # Calculate RS and RSI
            rs = avg_gain / avg_loss.replace(0, np.nan)
            rsi = 100 - (100 / (1 + rs))
            
            result = float(rsi.iloc[-1])
            return result if not pd.isna(result) else 50.0
            
        except Exception as e:
            print(f"RSI calculation error: {e}")
            return 50.0
    
    @staticmethod
    def calculate_ema(prices: pd.Series, period: int) -> float:
        """
        Calculate Exponential Moving Average (EMA)
        
        Pine Script equivalent: ta.ema(close, emaLength)
        
        Args:
            prices: Series of closing prices
            period: EMA period
        
        Returns:
            EMA value
        """
        if len(prices) < period:
            return float(prices.iloc[-1])  # Return last price if not enough data
        
        try:
            ema = prices.ewm(span=period, adjust=False).mean()
            result = float(ema.iloc[-1])
            return result if not pd.isna(result) else float(prices.iloc[-1])
            
        except Exception as e:
            print(f"EMA calculation error: {e}")
            return float(prices.iloc[-1])
    
    @staticmethod
    def calculate_sma(values: pd.Series, period: int) -> float:
        """
        Calculate Simple Moving Average (SMA)
        
        Pine Script equivalent: ta.sma(volume, volPeriod)
        
        Args:
            values: Series of values (price, volume, etc.)
            period: SMA period
        
        Returns:
            SMA value
        """
        if len(values) < period:
            return float(values.iloc[-1])
        
        try:
            sma = values.rolling(window=period).mean()
            result = float(sma.iloc[-1])
            return result if not pd.isna(result) else float(values.iloc[-1])
            
        except Exception as e:
            print(f"SMA calculation error: {e}")
            return float(values.iloc[-1])
    
    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
        """
        Calculate Average True Range (ATR)
        
        Args:
            df: DataFrame with 'high', 'low', 'close' columns
            period: ATR period (default: 14)
        
        Returns:
            ATR value
        """
        if len(df) < period + 1:
            return 0.0
        
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
            
            result = float(atr.iloc[-1])
            return result if not pd.isna(result) else 0.0
            
        except Exception as e:
            print(f"ATR calculation error: {e}")
            return 0.0
    
    @staticmethod
    def calculate_volatility(df: pd.DataFrame, period: int = 20) -> float:
        """
        Calculate volatility as standard deviation of returns
        
        Args:
            df: DataFrame with 'close' column
            period: Lookback period
        
        Returns:
            Volatility percentage
        """
        if len(df) < period:
            return 1.0
        
        try:
            returns = df['close'].pct_change().dropna()
            volatility = returns.tail(period).std() * 100
            
            return float(volatility) if not pd.isna(volatility) else 1.0
            
        except Exception as e:
            print(f"Volatility calculation error: {e}")
            return 1.0
    
    @staticmethod
    def is_bullish_candle(df: pd.DataFrame, index: int = -1) -> bool:
        """
        Check if candle is bullish (close > open)
        
        Pine Script equivalent: close > open
        
        Args:
            df: DataFrame with 'open' and 'close' columns
            index: Candle index (default: -1 for last candle)
        
        Returns:
            True if bullish candle
        """
        try:
            return float(df['close'].iloc[index]) > float(df['open'].iloc[index])
        except Exception:
            return False
    
    @staticmethod
    def is_bearish_candle(df: pd.DataFrame, index: int = -1) -> bool:
        """
        Check if candle is bearish (close < open)
        
        Pine Script equivalent: close < open
        
        Args:
            df: DataFrame with 'open' and 'close' columns
            index: Candle index (default: -1 for last candle)
        
        Returns:
            True if bearish candle
        """
        try:
            return float(df['close'].iloc[index]) < float(df['open'].iloc[index])
        except Exception:
            return False
    
    @staticmethod
    def is_strict_bullish_engulfing(df: pd.DataFrame) -> bool:
        """
        Check for strict bullish engulfing pattern
        
        Pine Script equivalent:
        (close > open) and (close[1] < open[1]) and 
        (close >= open[1]) and (open <= close[1])
        
        Requirements:
        - Current candle is bullish (close > open)
        - Previous candle is bearish (close[1] < open[1])
        - Current close >= previous open
        - Current open <= previous close
        
        Args:
            df: DataFrame with 'open' and 'close' columns
        
        Returns:
            True if strict bullish engulfing pattern detected
        """
        if len(df) < 2:
            return False
        
        try:
            # Current candle
            current_close = float(df['close'].iloc[-1])
            current_open = float(df['open'].iloc[-1])
            
            # Previous candle
            prev_close = float(df['close'].iloc[-2])
            prev_open = float(df['open'].iloc[-2])
            
            # Check all conditions
            current_bullish = current_close > current_open
            prev_bearish = prev_close < prev_open
            engulfs_top = current_close >= prev_open
            engulfs_bottom = current_open <= prev_close
            
            return current_bullish and prev_bearish and engulfs_top and engulfs_bottom
            
        except Exception as e:
            print(f"Bullish engulfing check error: {e}")
            return False
    
    @staticmethod
    def is_strict_bearish_engulfing(df: pd.DataFrame) -> bool:
        """
        Check for strict bearish engulfing pattern
        
        Pine Script equivalent:
        (close < open) and (close[1] > open[1]) and 
        (close <= open[1]) and (open >= close[1])
        
        Requirements:
        - Current candle is bearish (close < open)
        - Previous candle is bullish (close[1] > open[1])
        - Current close <= previous open
        - Current open >= previous close
        
        Args:
            df: DataFrame with 'open' and 'close' columns
        
        Returns:
            True if strict bearish engulfing pattern detected
        """
        if len(df) < 2:
            return False
        
        try:
            # Current candle
            current_close = float(df['close'].iloc[-1])
            current_open = float(df['open'].iloc[-1])
            
            # Previous candle
            prev_close = float(df['close'].iloc[-2])
            prev_open = float(df['open'].iloc[-2])
            
            # Check all conditions
            current_bearish = current_close < current_open
            prev_bullish = prev_close > prev_open
            engulfs_bottom = current_close <= prev_open
            engulfs_top = current_open >= prev_close
            
            return current_bearish and prev_bullish and engulfs_bottom and engulfs_top
            
        except Exception as e:
            print(f"Bearish engulfing check error: {e}")
            return False
    
    @staticmethod
    def calculate_all_indicators(df: pd.DataFrame, ema_period: int = 21, rsi_period: int = 14) -> dict:
        """
        Calculate all indicators for a given dataframe
        
        Args:
            df: DataFrame with OHLCV data
            ema_period: EMA period (default: 21)
            rsi_period: RSI period (default: 14)
        
        Returns:
            Dictionary with all calculated indicators
        """
        indicators = {}
        
        try:
            # Price indicators
            indicators['ema'] = TechnicalIndicators.calculate_ema(df['close'], ema_period)
            indicators['rsi'] = TechnicalIndicators.calculate_rsi(df['close'], rsi_period)
            
            # Volume indicators
            indicators['volume_sma'] = TechnicalIndicators.calculate_sma(df['volume'], 20)
            indicators['current_volume'] = float(df['volume'].iloc[-1])
            
            # Volatility
            indicators['atr'] = TechnicalIndicators.calculate_atr(df, 14)
            indicators['volatility'] = TechnicalIndicators.calculate_volatility(df, 20)
            
            # Price levels
            indicators['current_price'] = float(df['close'].iloc[-1])
            indicators['current_open'] = float(df['open'].iloc[-1])
            indicators['current_high'] = float(df['high'].iloc[-1])
            indicators['current_low'] = float(df['low'].iloc[-1])
            
            # Candle patterns
            indicators['is_bullish'] = TechnicalIndicators.is_bullish_candle(df)
            indicators['is_bearish'] = TechnicalIndicators.is_bearish_candle(df)
            indicators['bullish_engulfing'] = TechnicalIndicators.is_strict_bullish_engulfing(df)
            indicators['bearish_engulfing'] = TechnicalIndicators.is_strict_bearish_engulfing(df)
            
        except Exception as e:
            print(f"Error calculating indicators: {e}")
        
        return indicators
