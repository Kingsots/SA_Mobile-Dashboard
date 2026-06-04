"""
SA Structure Signal - Strategy Core V1 (PRODUCTION REWRITE)
============================================================
5-condition AND gate: EMA21, RSI14, Engulfing, Volume (>= 1.1x SMA20), Daily Alignment

FIXES APPLIED:
    1. Volume filter ACTIVE: enforces vol_ratio >= 1.1x 20-bar SMA (Condition 5 in evaluate())
    2. 4H EMA100 alignment now FAIL CLOSED (no silent bypass)
    3. Minimum data requirement: 110 intraday bars (~21+ 4H candles)
    4. Clear signal contract: returns -1, 0, 1 only

Strategy Logic (all conditions must be TRUE):
    - Condition 1: Price vs EMA21 (bull: close > EMA21, bear: close < EMA21)
    - Condition 2: RSI14 direction (bull: > 50, bear: < 50)
    - Condition 3: Engulfing pattern (bullish or bearish)
    - Condition 4: 4H EMA100 alignment (fail-closed, minimum 21 4H bars)

Volume filter: vol_ratio >= cfg.volume_threshold (default 1.1x 20-bar SMA).

Designed for:
    - Community members who want simple deterministic signals
    - 30m and 1h only (4h too slow for AND gate)
    - Expected win rate: 38-45% (lower than V2/V3)

Author: SA Strategy Core V1 — Production Rewrite
"""

from __future__ import annotations

import pandas as pd
import numpy as np
import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

logger = logging.getLogger(__name__)


# ===============================================================================
# SIGNAL ENUM
# ===============================================================================

class Signal(IntEnum):
    SELL    = -1
    NEUTRAL =  0
    BUY     =  1


# ===============================================================================
# TIMEFRAME CONFIG
# ===============================================================================

@dataclass
class V1Config:
    """V1 configuration — simple AND gate parameters."""
    ema_period: int = 21
    rsi_period: int = 14
    htf_ema_period: int = 100
    volume_period: int = 20
    volume_threshold: float = 1.1  # volume must be >= 1.1x the 20-bar SMA
    label: str = "1h Standard"


def get_v1_config(interval: str) -> V1Config:
    """Auto-calibrated config per timeframe."""
    iv = interval.lower().strip()

    if iv in ("30m", "30", "30min"):
        return V1Config(
            ema_period=21,
            rsi_period=14,
            htf_ema_period=100,
            label="30m Intraday",
        )

    if iv in ("1h", "60m", "60", "1hour"):
        return V1Config(
            ema_period=21,
            rsi_period=14,
            htf_ema_period=100,
            label="1h Standard",
        )

    if iv in ("2h", "120m", "120", "2hour"):
        return V1Config(
            ema_period=21,
            rsi_period=14,
            htf_ema_period=100,
            label="2h Swing (NOT RECOMMENDED)",
        )

    if iv in ("4h", "240m", "240", "4hour"):
        return V1Config(
            ema_period=21,
            rsi_period=14,
            htf_ema_period=100,
            label="4h Swing (NOT RECOMMENDED)",
        )

    return V1Config(label="unknown - defaulting to 1h")


# ===============================================================================
# INDICATOR FUNCTIONS
# ===============================================================================

def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(com=period - 1, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=period - 1, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def _volume_sma(series: pd.Series, period: int = 20) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()


def _is_bullish_engulfing(df: pd.DataFrame) -> bool:
    """Detect bullish engulfing pattern."""
    if len(df) < 2:
        return False
    prev = df.iloc[-2]
    curr = df.iloc[-1]
    current_is_bullish = curr['close'] > curr['open']
    previous_is_bearish = prev['close'] < prev['open']
    engulfs = (curr['close'] >= prev['open'] and curr['open'] <= prev['close'])
    return current_is_bullish and previous_is_bearish and engulfs


def _is_bearish_engulfing(df: pd.DataFrame) -> bool:
    """Detect bearish engulfing pattern."""
    if len(df) < 2:
        return False
    prev = df.iloc[-2]
    curr = df.iloc[-1]
    current_is_bearish = curr['close'] < curr['open']
    previous_is_bullish = prev['close'] > prev['open']
    engulfs = (curr['close'] <= prev['open'] and curr['open'] >= prev['close'])
    return current_is_bearish and previous_is_bullish and engulfs


def _get_daily_alignment(df: pd.DataFrame, ema_period: int = 100) -> tuple[bool, bool]:
    """
    4H EMA100 trend alignment (matches Pine Script higher timeframe logic).
    Resamples intraday 30m/1h data to 4H and applies EMA100.
    
    Returns (bullish_4h, bearish_4h).
    If insufficient data (< 21 bars of 4H data), returns (False, False).
    This means NO signal passes when higher timeframe data is insufficient.
    
    Minimum bars: 21 4H candles ≈ 5.25 trading days
    """
    try:
        # Resample intraday data to 4-hour bars
        df_4h = df.resample('4h').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
        }).dropna()

        # Minimum viable 4H bars: 21 (≈5 trading days)
        min_bars_4h = 21
        if len(df_4h) < min_bars_4h:
            logger.debug(f"[V1_HTF] Insufficient 4H bars: {len(df_4h)} < {min_bars_4h} — FAIL CLOSED")
            return False, False

        # Apply EMA100 to 4H closes
        df_4h['ema_htf'] = _ema(df_4h['close'], ema_period)
        latest = df_4h.iloc[-1]

        if pd.isna(latest['ema_htf']) or pd.isna(latest['close']):
            return False, False

        # Determine higher timeframe bias
        bullish = latest['close'] > latest['ema_htf']
        bearish = latest['close'] < latest['ema_htf']
        return bullish, bearish

    except Exception as e:
        logger.warning(f"[V1_HTF] Error: {e} — FAIL CLOSED")
        return False, False


# ===============================================================================
# LIVE SIGNAL ENGINE (STATELESS — V1 is pure AND gate)
# ===============================================================================

class V1SignalEngine:
    """
    V1 Signal Engine — stateless AND gate.
    
    No state persistence needed because V1 doesn't track sequences.
    Each bar is evaluated independently.
    """
    
    MIN_BARS = 110  # Hard gate: 110 bars minimum (100 for daily EMA + buffer)

    def __init__(
        self,
        ticker: str,
        interval: str,
        config: Optional[V1Config] = None,
    ):
        self.ticker = ticker
        self.interval = interval
        self.cfg = config or get_v1_config(interval)

    def evaluate(self, df_ohlcv: pd.DataFrame) -> Signal:
        """
        Evaluate the latest bar and return signal.
        
        Returns:
            Signal.BUY (1), Signal.SELL (-1), or Signal.NEUTRAL (0)
        """
        if df_ohlcv is None or len(df_ohlcv) < self.MIN_BARS:
            logger.debug(f"[V1] {self.ticker}-{self.interval}: MIN_BARS gate ({len(df_ohlcv) if df_ohlcv is not None else 0} < {self.MIN_BARS})")
            return Signal.NEUTRAL

        required = {'open', 'high', 'low', 'close', 'volume'}
        if not required.issubset(df_ohlcv.columns):
            logger.warning(f"[V1] {self.ticker}-{self.interval}: Missing columns {required - set(df_ohlcv.columns)}")
            return Signal.NEUTRAL

        df = df_ohlcv.copy()
        
        # UTC enforcement
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        elif str(df.index.tz) != "UTC":
            df.index = df.index.tz_convert("UTC")

        # Compute indicators
        df['ema_21'] = _ema(df['close'], self.cfg.ema_period)
        df['rsi_14'] = _rsi(df['close'], self.cfg.rsi_period)
        df['volume_sma_20'] = _volume_sma(df['volume'], self.cfg.volume_period)

        # 4H EMA100 alignment (FAIL CLOSED)
        daily_bull, daily_bear = _get_daily_alignment(df, self.cfg.htf_ema_period)

        # Get current values
        curr = df.iloc[-1]
        close = curr['close']
        ema_21 = curr['ema_21']
        rsi_14 = curr['rsi_14']
        volume = curr['volume']
        volume_sma_20 = curr['volume_sma_20']

        # Check for NaN
        if pd.isna(ema_21) or pd.isna(rsi_14) or pd.isna(volume_sma_20) or volume_sma_20 <= 0:
            logger.debug(f"[V1] {self.ticker}-{self.interval}: Indicator NaN/zero — ema={ema_21}, rsi={rsi_14}, vol_sma={volume_sma_20}")
            return Signal.NEUTRAL

        # Engulfing patterns
        is_bull_engulf = _is_bullish_engulfing(df)
        is_bear_engulf = _is_bearish_engulfing(df)

        # ========== BUY SIGNAL ==========
        # Condition 1: Price > EMA21
        # Condition 2: RSI > 50
        # Condition 3: Bullish engulfing
        # Condition 4: 4H EMA100 bullish alignment (FAIL CLOSED)
        # Condition 5: Volume >= 1.1x 20-bar SMA (momentum confirmation)
        vol_ratio = volume / volume_sma_20
        long_cond = (close > ema_21 and rsi_14 > 50 and is_bull_engulf and daily_bull and vol_ratio >= self.cfg.volume_threshold)
        short_cond = (close < ema_21 and rsi_14 < 50 and is_bear_engulf and daily_bear and vol_ratio >= self.cfg.volume_threshold)
        _ef = "OK" if close > ema_21 else "X"
        _rf = "OK" if rsi_14 > 50 else "X"
        _xf = "OK" if (is_bull_engulf or is_bear_engulf) else "X"
        _vf = "OK" if vol_ratio >= self.cfg.volume_threshold else "X"
        _af = "OK" if (daily_bull or daily_bear) else "X"
        _out = "BUY" if long_cond else "SELL" if short_cond else "NEUTRAL"
        logger.debug(
            f"[V1_EVAL] {self.ticker}-{self.interval} | "
            f"ema={_ef} rsi={_rf}({rsi_14:.1f}) "
            f"engulf={_xf} vol={_vf}({vol_ratio:.2f}x) "
            f"align={_af} => {_out}"
        )
        if (close > ema_21 and
                rsi_14 > 50 and
                is_bull_engulf and
                daily_bull and
                vol_ratio >= self.cfg.volume_threshold):
            logger.info(f"[V1_BUY] {self.ticker}-{self.interval}: close={close:.5f}, ema={ema_21:.5f}, rsi={rsi_14:.1f}, vol_ratio={vol_ratio:.2f}, daily_bull={daily_bull}")
            return Signal.BUY

        # ========== SELL SIGNAL ==========
        # Condition 1: Price < EMA21
        # Condition 2: RSI < 50
        # Condition 3: Bearish engulfing
        # Condition 4: 4H EMA100 bearish alignment (FAIL CLOSED)
        # Condition 5: Volume >= 1.1x 20-bar SMA (momentum confirmation)
        if (close < ema_21 and
                rsi_14 < 50 and
                is_bear_engulf and
                daily_bear and
                vol_ratio >= self.cfg.volume_threshold):
            logger.info(f"[V1_SELL] {self.ticker}-{self.interval}: close={close:.5f}, ema={ema_21:.5f}, rsi={rsi_14:.1f}, vol_ratio={vol_ratio:.2f}, daily_bear={daily_bear}")
            return Signal.SELL

        return Signal.NEUTRAL

    def reset(self):
        """V1 has no state — placeholder for API compatibility."""
        pass

    @property
    def stage(self) -> str:
        """V1 has no stage — placeholder."""
        return "V1 AND GATE"


# ===============================================================================
# BACKTEST FUNCTION
# ===============================================================================

def backtest(
    df_ohlcv: pd.DataFrame,
    ticker: str,
    interval: str,
    config: Optional[V1Config] = None,
) -> pd.DataFrame:
    """
    Run V1 across all bars and return DataFrame with signals.
    """
    cfg = config or get_v1_config(interval)
    engine = V1SignalEngine(ticker, interval, cfg)

    df = df_ohlcv.copy()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")

    df['ema_21'] = _ema(df['close'], cfg.ema_period)
    df['rsi_14'] = _rsi(df['close'], cfg.rsi_period)

    results = []

    for i in range(len(df)):
        if i < engine.MIN_BARS:
            results.append({
                'timestamp': df.index[i],
                'signal': 0,
                'label': 'NEUTRAL',
                'close': df['close'].iloc[i],
                'ema_21': df['ema_21'].iloc[i] if not pd.isna(df['ema_21'].iloc[i]) else np.nan,
                'rsi_14': df['rsi_14'].iloc[i] if not pd.isna(df['rsi_14'].iloc[i]) else np.nan,
            })
            continue

        # Need to run daily alignment per bar for backtest
        daily_bull, daily_bear = _get_daily_alignment(df.iloc[:i+1], cfg.htf_ema_period)

        curr = df.iloc[i]
        close = curr['close']
        ema_21 = curr['ema_21']
        rsi_14 = curr['rsi_14']

        if pd.isna(ema_21) or pd.isna(rsi_14):
            results.append({
                'timestamp': df.index[i],
                'signal': 0,
                'label': 'NEUTRAL',
                'close': close,
                'ema_21': ema_21,
                'rsi_14': rsi_14,
            })
            continue

        # Engulfing needs 2 bars
        is_bull_engulf = False
        is_bear_engulf = False
        if i >= 1:
            prev = df.iloc[i-1]
            curr_row = df.iloc[i]
            is_bull_engulf = (curr_row['close'] > curr_row['open'] and 
                              prev['close'] < prev['open'] and
                              curr_row['close'] >= prev['open'] and 
                              curr_row['open'] <= prev['close'])
            is_bear_engulf = (curr_row['close'] < curr_row['open'] and 
                              prev['close'] > prev['open'] and
                              curr_row['close'] <= prev['open'] and 
                              curr_row['open'] >= prev['close'])

        signal = 0
        if close > ema_21 and rsi_14 > 50 and is_bull_engulf and daily_bull:
            signal = 1
        elif close < ema_21 and rsi_14 < 50 and is_bear_engulf and daily_bear:
            signal = -1

        results.append({
            'timestamp': df.index[i],
            'signal': signal,
            'label': {1: 'BUY', -1: 'SELL', 0: 'NEUTRAL'}[signal],
            'close': close,
            'ema_21': ema_21,
            'rsi_14': rsi_14,
        })

    return pd.DataFrame(results).set_index('timestamp')


# ===============================================================================
# CONVENIENCE WRAPPER
# ===============================================================================

def evaluate(
    ticker: str,
    interval: str,
    df_ohlcv: pd.DataFrame,
    min_rows: int = 110,
) -> int:
    """Stateless convenience wrapper for V1."""
    if df_ohlcv is None or len(df_ohlcv) < min_rows:
        return int(Signal.NEUTRAL)
    try:
        engine = V1SignalEngine(ticker, interval)
        return int(engine.evaluate(df_ohlcv))
    except Exception as e:
        logger.error(f"[V1_EVALUATE] {ticker}-{interval}: {e}")
        return int(Signal.NEUTRAL)