"""
Trade Constructor - Builds complete TradeSignal objects from strategy output.

Takes:
- Strategy direction (1=BUY, -1=SELL, 0=NEUTRAL)
- Current OHLCV data
- Strategy name and confidence

Returns:
- Complete TradeSignal with realistic entry/SL/TP derived from price action
- Or None for NEUTRAL signals

Implementation (Breakout Confirmation Model):
- Entry: Signal candle high (BUY) or low (SELL) with breakout buffer
  - Converts signals to stop-entry breakout orders
  - Trades trigger only when price breaks signal candle
- Stop Loss: Rolling 3-bar structure (min/max) over last 5 bars
  - Professional swing-level placement
- Take Profit: 2:1 risk-reward ratio from breakout entry
"""

import pandas as pd
from typing import Optional
from datetime import datetime
import time

from signals.trade_signal import TradeSignal


# ═══════════════════════════════════════════════════════════════════════
# TRADE EXPIRY CONFIGURATION
# Defines how many candles a breakout order remains valid
# ═══════════════════════════════════════════════════════════════════════

EXPIRY_CANDLES = {
    "1m": 10,
    "5m": 8,
    "15m": 8,
    "30m": 6,
    "1h": 6,
    "4h": 5,
    "1d": 3
}


def interval_to_seconds(interval: str) -> int:
    """
    Convert interval string to seconds.
    
    Parameters:
    -----------
    interval : str
        Interval (e.g., '1m', '5m', '15m', '30m', '1h', '4h', '1d')
        
    Returns:
    --------
    int
        Number of seconds in interval
    """
    mapping = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "4h": 14400,
        "1d": 86400,
    }
    return mapping.get(interval, 3600)  # Default 1 hour


def build_trade_signal(
    ticker: str,
    interval: str,
    df_ohlcv: pd.DataFrame,
    direction: int,
    strategy_name: str,
    confidence: float = 1.0,
) -> Optional[TradeSignal]:
    """
    Build a complete trade signal from strategy output.
    
    Parameters:
    -----------
    ticker : str
        Currency pair (e.g., 'EURUSD')
    interval : str
        Timeframe (e.g., '1h', '4h')
    df_ohlcv : pd.DataFrame
        OHLCV dataframe with 'open', 'high', 'low', 'close', 'volume'
    direction : int
        Strategy output: 1=BUY, -1=SELL, 0=NEUTRAL
    strategy_name : str
        Name of strategy that generated signal
    confidence : float
        Confidence level (0.0-1.0)
    
    Returns:
    --------
    TradeSignal or None
        Complete trade signal, or None for NEUTRAL (direction==0)
    """
    
    # Return None for neutral signals
    if direction == 0:
        return None
    
    # Validate we have enough data
    if len(df_ohlcv) < 5:
        return None
    
    # ═══════════════════════════════════════════════════════════════════════
    # BREAKOUT CONFIRMATION ENTRY MODEL
    # Entry triggers when price breaks the signal candle high/low
    # ═══════════════════════════════════════════════════════════════════════
    
    # Signal candle is the last fully closed candle
    signal_candle = df_ohlcv.iloc[-1]
    signal_high = float(signal_candle['high'])
    signal_low = float(signal_candle['low'])
    
    # Extract signal candle timestamp and calculate expiry
    if 'timestamp' in signal_candle.index:
        signal_candle_dt = pd.Timestamp(signal_candle['timestamp'])
        signal_candle_time_int = int(signal_candle_dt.timestamp())
    else:
        # Fallback to index if no timestamp column
        signal_candle_dt = pd.Timestamp(signal_candle.name if hasattr(signal_candle, 'name') else df_ohlcv.index[-1])
        signal_candle_time_int = int(signal_candle_dt.timestamp())
    
    # Calculate expiry window based on interval
    expiry_candles_count = EXPIRY_CANDLES.get(interval, 6)
    interval_seconds = interval_to_seconds(interval)
    expiry_timestamp_int = signal_candle_time_int + (expiry_candles_count * interval_seconds)
    
    # Breakout buffer (0.0002 ≈ 2 pips on EURUSD at 1.1000)
    # Prevents micro-fakeouts and slippage
    breakout_buffer = signal_high * 0.0002  # Dynamic buffer based on price level
    
    # Entry price based on direction (stop-entry breakout level)
    if direction == 1:  # BUY
        # Entry = signal candle high + buffer (trade triggers above resistance)
        entry_price = signal_high + breakout_buffer
    elif direction == -1:  # SELL
        # Entry = signal candle low - buffer (trade triggers below support)
        entry_price = signal_low - breakout_buffer
    else:
        return None
    
    # Calculate stop loss using rolling swing structure (unchanged)
    # This creates professional, swing-level stops
    if direction == 1:  # BUY
        # For BUY: use rolling minimum (low pivot)
        rolling_lows = df_ohlcv['low'].rolling(window=3).min()
        # Take the minimum over last 5 bars
        stop_loss = float(rolling_lows.iloc[-5:].min())
        
    else:  # SELL (direction == -1)
        # For SELL: use rolling maximum (high pivot)
        rolling_highs = df_ohlcv['high'].rolling(window=3).max()
        # Take the maximum over last 5 bars
        stop_loss = float(rolling_highs.iloc[-5:].max())
    
    # Calculate risk distance and take profit from breakout entry
    risk_distance = abs(entry_price - stop_loss)
    
    if direction == 1:  # BUY
        # TP is 2x risk distance above entry
        take_profit = entry_price + (2 * risk_distance)
    else:  # SELL
        # TP is 2x risk distance below entry
        take_profit = entry_price - (2 * risk_distance)
    
    # Recalculate risk-reward ratio
    reward_distance = abs(take_profit - entry_price)
    risk_reward_ratio = reward_distance / risk_distance if risk_distance > 0 else 2.0
    
    # Create and return the trade signal
    signal = TradeSignal(
        ticker=ticker,
        interval=interval,
        direction=direction,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_reward=risk_reward_ratio,  # Recalculated from breakout entry
        strategy=strategy_name,
        confidence=confidence,
        timestamp=datetime.utcnow(),
        created_at=datetime.utcnow(),
        entry_type='breakout_confirmation',  # Mark entry model type
        signal_candle_time=signal_candle_time_int,  # Signal candle unix timestamp
        expiry_timestamp=expiry_timestamp_int,  # When breakout order expires
        expiry_candles=expiry_candles_count,  # Number of candles until expiry
    )
    
    return signal
