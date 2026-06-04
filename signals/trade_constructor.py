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
import logging
from core.config import Config



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




def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """
    Calculate Wilder's ATR (Average True Range) using EWM.
    
    Parameters:
    -----------
    df : pd.DataFrame
        OHLCV dataframe with 'high', 'low', 'close' columns
    period : int
        ATR period (default 14)
    
    Returns:
    --------
    float
        Current ATR value
    """
    high, low, close = df['high'], df['low'], df['close']
    prev_close = close.shift(1)
    
    # Calculate True Range
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    
    # Exponential Moving Average of True Range
    atr = tr.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    return float(atr.iloc[-1])


def build_trade_signal(
    ticker: str,
    interval: str,
    df_ohlcv: pd.DataFrame,
    direction: int,
    strategy_name: str,
    confidence: float = 1.0,
    signal_bar_index: Optional[int] = None,
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

    logger = logging.getLogger(__name__)
    logger.info(f"[BUILD_DEBUG] START | ticker={ticker}, direction={direction}, interval={interval}")
    logger.info(f"[BUILD_DEBUG] df_ohlcv shape: {df_ohlcv.shape if df_ohlcv is not None else 'None'}")

    
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
    
    # Signal candle is the bar that triggered the signal
    # If signal_bar_index is provided, use it; otherwise fall back to last bar (for V1 and backward compat)
    if signal_bar_index is not None and 0 <= signal_bar_index < len(df_ohlcv):
        signal_candle = df_ohlcv.iloc[signal_bar_index]
    else:
        signal_candle = df_ohlcv.iloc[-1]  # Fallback for V1 and other callers
    
    signal_high = float(signal_candle['high'])
    signal_low = float(signal_candle['low'])
    
    # Debug logging for signal bar index tracking
    if signal_bar_index is not None:
        logger.info(f"[ENTRY_DEBUG] {ticker}-{interval} | Using bar index {signal_bar_index} for entry calculation")
    
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
    logger.info(f"[BUILD_DEBUG] entry_price calculated: {entry_price}")
    
    # Calculate Wilder's ATR for stop loss sizing
    atr_value = calculate_atr(df_ohlcv, period=14)
    logger.info(f"[BUILD_DEBUG] atr_value calculated: {atr_value}")
    _atr_mult = getattr(Config, 'ATR_MULTIPLIER', 1.5)
    atr_buffer = atr_value * _atr_mult

    if direction == 1:   # BUY
        # Stop below signal candle low — structural anchor
        stop_loss   = signal_low - atr_buffer
    else:                # SELL
        # Stop above signal candle high — structural anchor
        stop_loss   = signal_high + atr_buffer

    # SL cap: prevent outlier stops on low-priced tokens
    _sl_max_pct = getattr(Config, 'SL_MAX_PCT', 0.08)
    _max_sl_distance = entry_price * _sl_max_pct
    _actual_sl_distance = abs(entry_price - stop_loss)
    if _actual_sl_distance > _max_sl_distance:
        # Cap the stop -- move it to the maximum allowed distance
        if stop_loss < entry_price:  # BUY
            stop_loss = entry_price - _max_sl_distance
        else:                        # SELL
            stop_loss = entry_price + _max_sl_distance
        logging.info(
            f'[SL_CAP] {ticker} {interval}: '
            f'ATR stop {_actual_sl_distance:.4f} '
            f'capped to {_max_sl_distance:.4f} '
            f'({_sl_max_pct*100:.1f}% of entry)'
        )

    if direction == 1:
        risk        = entry_price - stop_loss
        take_profit = entry_price + (risk * 2.0)   # 2:1 R:R from entry
    else:
        risk        = stop_loss - entry_price
        take_profit = entry_price - (risk * 2.0)   # 2:1 R:R from entry

    # Calculate risk-reward ratio from ATR-based stops
    logger.info(f"[BUILD_DEBUG] FINAL | stop_loss={stop_loss}, take_profit={take_profit}, entry={entry_price}")
    risk_distance = abs(entry_price - stop_loss)
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
        atr_value=atr_value,
    )
    
    return signal


# ═══════════════════════════════════════════════════════════════════
# FLOW ENGINE — TRADE CONSTRUCTOR
# build_flow_trade_signal()
# OptiCore Labs · Silent Analyst · Added: May 25 2026
#
# Transforms a FlowSignal (detection output) into a TradeSignal
# (execution output) with structural SL and 3R TP.
#
# STOP LOSS — STRUCTURAL (not pure ATR):
#   LONG:  min(candle_low, key_level) - (ATR14 * buffer)
#   SHORT: max(candle_high, key_level) + (ATR14 * buffer)
#   Cap:   abs(entry - stop) <= entry * FLOW_SL_MAX_PCT
#
# TAKE PROFIT — 3R:
#   LONG:  entry + (risk * FLOW_TP_MULTIPLIER)
#   SHORT: entry - (risk * FLOW_TP_MULTIPLIER)
#
# HIGH CONVICTION encoding (no metadata field on TradeSignal):
#   entry_type = 'flow_high_conviction' or 'flow_breakout'
#   confidence = 1.0  (Flow signals are fully deterministic)
#   strategy   = 'strategy_core_flow'
# ═══════════════════════════════════════════════════════════════════

def build_flow_trade_signal(
    flow_signal,
    config=None
) -> Optional[TradeSignal]:
    """
    Build a TradeSignal from a FlowSignal detection result.

    Args:
        flow_signal: FlowSignal instance from strategy_core_flow.py
        config:      Optional FlowConfig. If None, reads from
                     core.config.Config directly.

    Returns:
        TradeSignal on success.
        None if risk validation fails (zero risk, SL cap exceeded,
        or SL crosses entry price).

    Stop loss formula (structural invalidation):
        LONG:  min(candle_low, key_level) - (ATR14 * buffer)
        SHORT: max(candle_high, key_level) + (ATR14 * buffer)

    This anchors risk to the structural line in the sand -
    not to a projected ATR band from the current price.
    If price re-enters the break zone, the setup has failed.
    """
    from uuid import uuid4

    # ── RESOLVE CONFIG VALUES ─────────────────────────────────────
    try:
        if config is not None:
            stop_atr_buffer = config.stop_atr_buffer \
                if hasattr(config, 'stop_atr_buffer') \
                else Config.FLOW_STOP_ATR_BUFFER
            sl_max_pct      = config.sl_max_pct \
                if hasattr(config, 'sl_max_pct') \
                else Config.FLOW_SL_MAX_PCT
            tp_multiplier   = config.tp_multiplier \
                if hasattr(config, 'tp_multiplier') \
                else Config.FLOW_TP_MULTIPLIER
            strategy_version = getattr(
                config, 'strategy_version', Config.FLOW_STRATEGY_VERSION
            )
        else:
            stop_atr_buffer  = Config.FLOW_STOP_ATR_BUFFER
            sl_max_pct       = Config.FLOW_SL_MAX_PCT
            tp_multiplier    = Config.FLOW_TP_MULTIPLIER
            strategy_version = Config.FLOW_STRATEGY_VERSION
    except Exception as e:
        logging.error(f"[FLOW_CONSTRUCTOR] Config resolution failed: {e}")
        return None

    entry       = float(flow_signal.entry)
    atr_14      = float(flow_signal.atr_14)
    direction   = int(flow_signal.direction)   # 1=LONG, -1=SHORT
    candle_low  = float(flow_signal.candle_low)
    candle_high = float(flow_signal.candle_high)
    key_level   = float(flow_signal.key_level)

    # ── GUARD: ATR must be positive ───────────────────────────────
    if atr_14 <= 0:
        logging.warning(
            f"[FLOW_CONSTRUCTOR] {flow_signal.symbol}: "
            f"ATR14 is zero or negative ({atr_14}) — rejected"
        )
        return None

    # ── STRUCTURAL STOP LOSS ──────────────────────────────────────
    # Anchor to the lower of the break candle low and the key level,
    # then add an ATR buffer below for volatility clearance.
    # This places the stop at structural invalidation, not ATR alone.
    if direction == 1:   # LONG
        structural_anchor = min(candle_low, key_level)
        stop_loss         = structural_anchor - (atr_14 * stop_atr_buffer)
    else:                # SHORT
        structural_anchor = max(candle_high, key_level)
        stop_loss         = structural_anchor + (atr_14 * stop_atr_buffer)

    # ── RISK CALCULATION ──────────────────────────────────────────
    risk = abs(entry - stop_loss)

    # Guard: zero risk
    if risk <= 0:
        logging.warning(
            f"[FLOW_CONSTRUCTOR] {flow_signal.symbol}: "
            f"zero risk — entry={entry} stop={stop_loss} — rejected"
        )
        return None

    # Guard: SL cap — stop cannot be more than FLOW_SL_MAX_PCT from entry
    max_risk = entry * sl_max_pct
    if risk > max_risk:
        logging.warning(
            f"[FLOW_CONSTRUCTOR] {flow_signal.symbol}: "
            f"SL distance {risk/entry*100:.2f}% exceeds cap "
            f"{sl_max_pct*100:.1f}% — rejected"
        )
        return None

    # Guard: SL must not cross entry price
    if direction == 1 and stop_loss >= entry:
        logging.warning(
            f"[FLOW_CONSTRUCTOR] {flow_signal.symbol}: "
            f"LONG SL {stop_loss} >= entry {entry} — rejected"
        )
        return None
    if direction == -1 and stop_loss <= entry:
        logging.warning(
            f"[FLOW_CONSTRUCTOR] {flow_signal.symbol}: "
            f"SHORT SL {stop_loss} <= entry {entry} — rejected"
        )
        return None

    # ── TAKE PROFIT (3R) ──────────────────────────────────────────
    if direction == 1:   # LONG
        take_profit = entry + (risk * tp_multiplier)
    else:                # SHORT
        take_profit = entry - (risk * tp_multiplier)

    # ── R:R (always tp_multiplier by construction = 3.0) ─────────
    risk_reward = tp_multiplier

    # ── HIGH CONVICTION ENCODING ──────────────────────────────────
    # TradeSignal has no metadata or high_conviction field.
    # Encode via entry_type (semantically correct — classifies setup)
    # and confidence (1.0 — Flow signals are fully deterministic).
    entry_type = (
        'flow_high_conviction'
        if flow_signal.high_conviction
        else 'flow_breakout'
    )

    # ── TRADE ID ──────────────────────────────────────────────────
    trade_id = 'FLOW-' + uuid4().hex[:4].upper()

    # ── SIGNAL CANDLE TIME ────────────────────────────────────────
    try:
        signal_candle_time = int(
            flow_signal.timestamp.timestamp() * 1000
        )
    except Exception:
        signal_candle_time = None

    # ── CONSTRUCT TradeSignal ─────────────────────────────────────
    signal = TradeSignal(
        ticker             = flow_signal.symbol,
        interval           = flow_signal.interval,
        strategy           = 'strategy_core_flow',
        direction          = direction,
        entry_price        = round(entry, 8),
        stop_loss          = round(stop_loss, 8),
        take_profit        = round(take_profit, 8),
        risk_reward        = round(risk_reward, 2),
        confidence         = 1.0,
        entry_type         = entry_type,
        signal_candle_time = signal_candle_time,
        expiry_candles     = 6,
        atr_value          = round(atr_14, 8),
        trade_id           = trade_id,
    )

    logging.info(
        f"[FLOW_CONSTRUCTOR] {flow_signal.symbol} {flow_signal.interval} "
        f"{'LONG' if direction == 1 else 'SHORT'} | "
        f"entry={entry:.6f} SL={stop_loss:.6f} TP={take_profit:.6f} | "
        f"risk={risk/entry*100:.2f}% | RR={risk_reward:.1f}R | "
        f"{'★ HIGH_CONVICTION' if flow_signal.high_conviction else 'standard'}"
    )

    return signal
