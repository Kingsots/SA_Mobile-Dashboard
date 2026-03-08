"""
SA RSI Break and Retest - Strategy Core v2
==========================================
Production-grade Python port of Pine Script v6 logic.

Architecture:
    - Stateful signal engine with full RSI sequence tracking
    - Timeframe-aware parameter auto-configuration
    - Two-stage entry: RSI sequence (Stage 1) + EMA body break (Stage 2)
    - Fail-closed daily alignment (no silent filter bypass)
    - No volume dependency (unreliable on forex)
    - Pure function interface: evaluate() returns -1, 0, 1

Designed for:
    - Forex intraday (30m, 45m, 1h) and swing (2h, 4h)
    - Quant trading firm production deployment
    - Clean integration with any execution or signal storage layer

Author: SA Strategy Core v2
"""

from __future__ import annotations

import pandas as pd
import numpy as np
import logging
from dataclasses import dataclass, field
from typing import Optional
# Lazy import: log_stage_transition imported at call site
from enum import IntEnum

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
# Auto-calibrated per timeframe. Override via TimeframeConfig if needed.
# Mirrors Pine Script v6 autoExtremeZone / autoBullLevel logic exactly.
# ===============================================================================

@dataclass
class TimeframeConfig:
    """
    RSI and entry parameters calibrated per timeframe.

    On faster timeframes (30m):
        - RSI extreme zone is shallower (38) -- momentum setups don't need deep oversold
        - Break levels are wider (43/57) -- more room for noise
        - Retest tolerance shorter (4 bars) -- momentum is fast
        - Entry window shorter (6 bars) -- EMA cross comes quickly

    On slower timeframes (2h):
        - RSI extreme zone is deeper (40) -- swing setups breathe more
        - Break levels tighter (44/56) -- larger candles, less noise needed
        - Retest tolerance longer (6 bars) -- RSI moves slower relative to price
        - Entry window longer (10 bars) -- price takes time to commit to EMA
    """
    # RSI settings
    rsi_period:          int   = 14
    rsi_extreme_bull:    int   = 35    # RSI must visit below this to arm bull
    rsi_extreme_bear:    int   = 65    # RSI must visit above this to arm bear
    rsi_bull_break:      int   = 45    # RSI break level for bull setup
    rsi_bear_break:      int   = 55    # RSI break level for bear setup
    rsi_retest_buffer:   float = 1.0   # +/- pts around break level for retest
    rsi_retest_bars:     int   = 5     # max bars to retest after break
    rsi_extreme_reset:   int   = 50    # bars of inactivity before extreme flag expires

    # Stage 2 entry
    entry_window_bars:   int   = 8     # bars after retest to find EMA body break

    # EMA
    ema_period:          int   = 21    # LTF EMA for entry confirmation
    htf_ema_period:      int   = 100   # Daily EMA for trend alignment

    # Structure risk
    swing_lookback:      int   = 10    # pivot high/low lookback for SL placement
    sl_buffer_pct:       float = 0.05  # % buffer beyond swing for SL
    rr_ratio:            float = 2.0   # R:R for TP projection

    label: str = "custom"


def get_timeframe_config(interval: str) -> TimeframeConfig:
    """
    Auto-detect and return calibrated config for given interval string.

    Supported intervals: '30m', '45m', '1h', '2h', '4h', '1d'
    Falls back to 1h config for unknown intervals.

    Pine Script mirror:
        tfMins <= 30  -> 30m config
        tfMins <= 45  -> 45m config
        tfMins <= 60  -> 1h config
        tfMins <= 120 -> 2h config
        else          -> HTF config
    """
    iv = interval.lower().strip()

    if iv in ('30m', '30', '30min'):
        return TimeframeConfig(
            rsi_extreme_bull  = 38,
            rsi_extreme_bear  = 62,
            rsi_bull_break    = 43,
            rsi_bear_break    = 57,
            rsi_retest_buffer = 1.5,
            rsi_retest_bars   = 4,
            rsi_extreme_reset = 40,
            entry_window_bars = 6,
            label             = "30m Intraday",
        )

    if iv in ('45m', '45', '45min'):
        return TimeframeConfig(
            rsi_extreme_bull  = 37,
            rsi_extreme_bear  = 63,
            rsi_bull_break    = 44,
            rsi_bear_break    = 56,
            rsi_retest_buffer = 1.5,
            rsi_retest_bars   = 5,
            rsi_extreme_reset = 50,
            entry_window_bars = 7,
            label             = "45m Intraday",
        )

    if iv in ('1h', '60m', '60', '1hour'):
        return TimeframeConfig(
            rsi_extreme_bull  = 35,
            rsi_extreme_bear  = 65,
            rsi_bull_break    = 45,
            rsi_bear_break    = 55,
            rsi_retest_buffer = 1.5,        # Widened from 1.0 to improve Stage 1C conversion
            rsi_retest_bars   = 5,
            rsi_extreme_reset = 50,
            entry_window_bars = 8,
            label             = "1h Standard",
        )

    if iv in ('2h', '120m', '120', '2hour'):
        return TimeframeConfig(
            rsi_extreme_bull  = 40,
            rsi_extreme_bear  = 60,
            rsi_bull_break    = 44,
            rsi_bear_break    = 56,
            rsi_retest_buffer = 2.0,
            rsi_retest_bars   = 6,
            rsi_extreme_reset = 60,
            entry_window_bars = 10,
            label             = "2h Swing",
        )

    if iv in ('4h', '240m', '240', '4hour'):
        return TimeframeConfig(
            rsi_extreme_bull  = 40,
            rsi_extreme_bear  = 60,
            rsi_bull_break    = 44,
            rsi_bear_break    = 56,
            rsi_retest_buffer = 2.0,
            rsi_retest_bars   = 6,
            rsi_extreme_reset = 60,
            entry_window_bars = 12,
            label             = "4h Swing",
        )

    # Default fallback: treat as 1h
    return TimeframeConfig(label="unknown - defaulting to 1h")


# ===============================================================================
# STATE MACHINE
# Tracks RSI sequence across bars. Must persist between bar evaluations.
# One instance per (ticker, interval) pair.
# ===============================================================================

@dataclass
class SequenceState:
    """
    Mutable state machine that mirrors Pine Script var declarations.
    Tracks the two-stage RSI Break and Retest sequence.

    Stage 1 - RSI Sequence:
        Step A: RSI visits extreme zone  -> arms bull/bear flag
        Step B: RSI breaks level         -> bullBreakBar / bearBreakBar set
        Step C: RSI retests level        -> bullRetestDone / bearRetestDone set

    Stage 2 - Entry Window:
        After retest: entry window opens for EMA body break confirmation
        If EMA body break fires within window -> signal
        If window expires -> full reset, back to scanning
    """

    # Stage 1A - extreme visit
    bull_extreme_visited: bool = False
    bear_extreme_visited: bool = False
    extreme_bar:          int  = 0

    # Stage 1B - break
    bull_break_bar:  Optional[int] = None
    bear_break_bar:  Optional[int] = None

    # Stage 1C - retest
    bull_retest_done: bool         = False
    bear_retest_done: bool         = False
    bull_retest_bar:  Optional[int] = None
    bear_retest_bar:  Optional[int] = None

    # Stage 2 - entry window
    bull_entry_armed:      bool         = False
    bear_entry_armed:      bool         = False
    bull_entry_window_bar: Optional[int] = None
    bear_entry_window_bar: Optional[int] = None

    def reset_bull(self):
        """Full bull setup reset - back to scanning."""
        self.bull_extreme_visited  = False
        self.bull_break_bar        = None
        self.bull_retest_done      = False
        self.bull_retest_bar       = None
        self.bull_entry_armed      = False
        self.bull_entry_window_bar = None

    def reset_bear(self):
        """Full bear setup reset - back to scanning."""
        self.bear_extreme_visited  = False
        self.bear_break_bar        = None
        self.bear_retest_done      = False
        self.bear_retest_bar       = None
        self.bear_entry_armed      = False
        self.bear_entry_window_bar = None

    @property
    def stage_description(self) -> str:
        """Human-readable state for logging and dashboard."""
        if self.bull_entry_armed:
            return "BULL: ENTRY WINDOW OPEN - WATCH EMA"
        if self.bull_retest_done:
            return "BULL: RETEST DONE - ENTRY WINDOW OPENING"
        if self.bull_break_bar is not None:
            return "BULL: RSI BREAK - WAIT RETEST"
        if self.bear_entry_armed:
            return "BEAR: ENTRY WINDOW OPEN - WATCH EMA"
        if self.bear_retest_done:
            return "BEAR: RETEST DONE - ENTRY WINDOW OPENING"
        if self.bear_break_bar is not None:
            return "BEAR: RSI BREAK - WAIT RETEST"
        return "SCANNING"

    def to_dict(self) -> dict:
        """Convert state to dict for database persistence."""
        return {
            'bull_extreme_visited': self.bull_extreme_visited,
            'bear_extreme_visited': self.bear_extreme_visited,
            'extreme_bar': self.extreme_bar,
            'bull_break_bar': self.bull_break_bar,
            'bear_break_bar': self.bear_break_bar,
            'bull_retest_done': self.bull_retest_done,
            'bear_retest_done': self.bear_retest_done,
            'bull_retest_bar': self.bull_retest_bar,
            'bear_retest_bar': self.bear_retest_bar,
            'bull_entry_armed': self.bull_entry_armed,
            'bear_entry_armed': self.bear_entry_armed,
            'bull_entry_window_bar': self.bull_entry_window_bar,
            'bear_entry_window_bar': self.bear_entry_window_bar,
        }

    @classmethod
    def from_dict(cls, state_dict: dict) -> 'SequenceState':
        """Reconstruct state from persistence dict."""
        if not state_dict:
            return cls()
        
        return cls(
            bull_extreme_visited=state_dict.get('bull_extreme_visited', False),
            bear_extreme_visited=state_dict.get('bear_extreme_visited', False),
            extreme_bar=state_dict.get('extreme_bar', 0),
            bull_break_bar=state_dict.get('bull_break_bar'),
            bear_break_bar=state_dict.get('bear_break_bar'),
            bull_retest_done=state_dict.get('bull_retest_done', False),
            bear_retest_done=state_dict.get('bear_retest_done', False),
            bull_retest_bar=state_dict.get('bull_retest_bar'),
            bear_retest_bar=state_dict.get('bear_retest_bar'),
            bull_entry_armed=state_dict.get('bull_entry_armed', False),
            bear_entry_armed=state_dict.get('bear_entry_armed', False),
            bull_entry_window_bar=state_dict.get('bull_entry_window_bar'),
            bear_entry_window_bar=state_dict.get('bear_entry_window_bar'),
        )


# ===============================================================================
# DUAL-PATH CONFIRMATION SYSTEM
# MODE 1: Trend Continuation (requires daily alignment)
# MODE 2: Counter-Trend Sniper (activates when daily alignment fails, higher thresholds)
# ===============================================================================

@dataclass
class ConfirmationResult:
    """
    Result of dual-path confirmation evaluation.
    
    Attributes:
        approved: True if either trend_continuation or counter_trend approved
        mode: "trend_continuation", "counter_trend", or None
        position_size_multiplier: 1.0 (normal) or 0.5 (reduced for counter-trend)
        reason: Human-readable explanation for logging
    """
    approved: bool
    mode: Optional[str]  # "trend_continuation", "counter_trend", None
    position_size_multiplier: float = 1.0
    reason: str = ""


def evaluate_trend_continuation(
    window_open: bool,
    body_valid: bool,
    daily_aligned: bool,
    rsi_val: float,
    cfg: TimeframeConfig,
) -> ConfirmationResult:
    """
    MODE 1: Trend Continuation - Classic approach requiring daily alignment.
    
    Requires:
    - Entry window open
    - Body break confirmed
    - Daily trend alignment (daily EMA indicates direction match)
    
    Returns:
        ConfirmationResult with mode="trend_continuation" if approved, else None
    """
    if not (window_open and body_valid and daily_aligned):
        return ConfirmationResult(
            approved=False,
            mode=None,
            reason="Trend continuation blocked: missing condition(s)"
        )
    
    # All conditions met
    return ConfirmationResult(
        approved=True,
        mode="trend_continuation",
        position_size_multiplier=1.0,
        reason="Trend continuation: daily aligned entry"
    )


def evaluate_counter_trend(
    window_open: bool,
    body_valid: bool,
    daily_failed: bool,
    rsi_val: float,
    rsi_extreme: bool,
    cfg: TimeframeConfig,
    counter_trend_rsi_extreme: float = 20.0,
) -> ConfirmationResult:
    """
    MODE 2: Counter-Trend Sniper - Activates only when daily alignment fails.
    
    Additional strict requirements:
    - Entry window open
    - Body break valid
    - Daily alignment FAILED (both daily_bull and daily_bear are False)
    - RSI in extreme zone (< 20 for bull counter-trend, > 80 for bear)
    - Must exceed basic RSI extreme threshold
    
    Returns:
        ConfirmationResult with mode="counter_trend" if approved, else None
        
    Position size is automatically reduced to 50% for risk management.
    """
    
    # Only activate if BOTH daily conditions failed (initialization flaw, not normal uptrend)
    if not daily_failed:
        return ConfirmationResult(
            approved=False,
            mode=None,
            reason="Counter-trend not applicable: daily alignment data available"
        )
    
    # Entry window and body must still be valid
    if not (window_open and body_valid):
        return ConfirmationResult(
            approved=False,
            mode=None,
            reason="Counter-trend blocked: window or body invalid"
        )
    
    # RSI must be in genuine extreme (> counter_trend_rsi_extreme threshold)
    # For bullish counter-trend, RSI should be very low (< 20)
    # For bearish counter-trend, RSI should be very high (> 80)
    # Since this function doesn't know direction yet, we check asymmetric extremes
    rsi_threshold_bull = 100.0 - counter_trend_rsi_extreme  # ~80 for > 80 check
    rsi_threshold_bear = counter_trend_rsi_extreme           # ~20 for < 20 check
    
    is_rsi_extreme = (rsi_val < rsi_threshold_bear) or (rsi_val > rsi_threshold_bull)
    
    if not is_rsi_extreme:
        return ConfirmationResult(
            approved=False,
            mode=None,
            reason=f"Counter-trend blocked: RSI={rsi_val:.1f} not extreme enough (need <20 or >80)"
        )
    
    # All strict conditions met
    return ConfirmationResult(
        approved=True,
        mode="counter_trend",
        position_size_multiplier=0.5,  # Halved position for counter-trend risk
        reason="Counter-trend sniper: extreme RSI + daily alignment gap"
    )


# ===============================================================================
# INDICATOR FUNCTIONS
# Pure, stateless. Same math as Pine Script built-ins.
# ===============================================================================

def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0).ewm(com=period - 1, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=period - 1, adjust=False).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def _pivot_high(high: pd.Series, lookback: int) -> pd.Series:
    """Returns pivot high value at confirmed pivot bars, else NaN."""
    result = pd.Series(np.nan, index=high.index)
    for i in range(lookback, len(high) - lookback):
        window = high.iloc[i - lookback: i + lookback + 1]
        if high.iloc[i] == window.max():
            result.iloc[i] = high.iloc[i]
    return result


def _pivot_low(low: pd.Series, lookback: int) -> pd.Series:
    """Returns pivot low value at confirmed pivot bars, else NaN."""
    result = pd.Series(np.nan, index=low.index)
    for i in range(lookback, len(low) - lookback):
        window = low.iloc[i - lookback: i + lookback + 1]
        if low.iloc[i] == window.min():
            result.iloc[i] = low.iloc[i]
    return result


def _full_body_bull(row_open: float, row_close: float, ema: float) -> bool:
    """
    Full body bullish candle above EMA.
    Both open AND close above EMA, close > open.
    Mirrors Pine Script: (open > emaVal) and (close > emaVal) and (close > open)
    """
    return (row_open > ema) and (row_close > ema) and (row_close > row_open)


def _full_body_bear(row_open: float, row_close: float, ema: float) -> bool:
    """
    Full body bearish candle below EMA.
    Both open AND close below EMA, close < open.
    Mirrors Pine Script: (open < emaVal) and (close < emaVal) and (close < open)
    """
    return (row_open < ema) and (row_close < ema) and (row_close < row_open)


def _get_daily_alignment(
    df: pd.DataFrame,
    htf_ema_period: int = 100
) -> tuple[bool, bool]:
    """
    Daily EMA100 trend alignment.

    Returns:
        (daily_bullish, daily_bearish)

    FAIL CLOSED: If insufficient daily data, returns (False, False).
    This means signals are suppressed, not silently passed through.
    The caller must handle this case explicitly.

    This is the critical difference from v1 which returned (True, True)
    and silently disabled the most important filter in the system.
    """
    try:
        df_daily = df.resample('4H').agg({
            'open':  'first',
            'high':  'max',
            'low':   'min',
            'close': 'last',
        }).dropna()

        if len(df_daily) < htf_ema_period:
            # Fail closed: not enough data to form a reliable daily EMA
            return False, False

        df_daily['ema_htf'] = _ema(df_daily['close'], htf_ema_period)
        latest = df_daily.iloc[-1]

        if pd.isna(latest['ema_htf']) or pd.isna(latest['close']):
            return False, False

        bullish = latest['close'] > latest['ema_htf']
        bearish = latest['close'] < latest['ema_htf']
        return bullish, bearish

    except Exception:
        return False, False


# ===============================================================================
# STATELESS BATCH EVALUATOR
# For backtesting: runs the full state machine across all bars in a DataFrame.
# Returns a Series of signals aligned to the DataFrame index.
# ===============================================================================

def backtest(
    df_ohlcv:   pd.DataFrame,
    interval:   str,
    config:     Optional[TimeframeConfig] = None,
    use_htf:    bool = True,
) -> pd.DataFrame:
    """
    Run the full RSI Break and Retest state machine across all bars.

    Returns a DataFrame with columns:
        signal       : -1, 0, 1
        stage        : human-readable state at each bar
        rsi          : RSI value
        ema_21       : LTF EMA value
        bull_extreme : bool - bull extreme visited flag
        bear_extreme : bool - bear extreme visited flag
        sl           : structure-based stop loss price (nan if not set)
        tp           : take profit price (nan if not set)

    Use this for:
        - Historical performance validation
        - Parameter tuning across timeframes
        - Signal distribution analysis (% BUY / SELL / NEUTRAL)
    """
    cfg   = config or get_timeframe_config(interval)
    state = SequenceState()

    df = df_ohlcv.copy()
    df['ema_21']  = _ema(df['close'], cfg.ema_period)
    df['rsi']     = _rsi(df['close'], cfg.rsi_period)
    df['ph']      = _pivot_high(df['high'], cfg.swing_lookback)
    df['pl']      = _pivot_low(df['low'],  cfg.swing_lookback)

    # Pre-compute daily alignment once (uses full df)
    if use_htf:
        daily_bull, daily_bear = _get_daily_alignment(df, cfg.htf_ema_period)
    else:
        daily_bull, daily_bear = True, True

    # Rolling pivot tracking
    last_swing_high = np.nan
    last_swing_low  = np.nan

    results = []

    for i in range(len(df)):
        row      = df.iloc[i]
        bar_idx  = i
        rsi_val  = row['rsi']
        ema_val  = row['ema_21']

        if pd.isna(rsi_val) or pd.isna(ema_val):
            results.append(_null_result(state))
            continue

        # Update swing points
        if not pd.isna(row['ph']):
            last_swing_high = row['ph']
        if not pd.isna(row['pl']):
            last_swing_low = row['pl']

        # -- Stage 1A: Extreme zone tracking ----------------------------------
        # Extreme flag expires after inactivity
        if (bar_idx - state.extreme_bar) > cfg.rsi_extreme_reset:
            state.bull_extreme_visited = False
            state.bear_extreme_visited = False

        # Visiting bull extreme cancels bear and vice versa (mutually exclusive)
        if rsi_val <= cfg.rsi_extreme_bull:
            if not state.bull_extreme_visited:
                logger.info(f"[V2_STAGE_1A] BULL EXTREME ZONE VISITED: RSI={rsi_val:.2f} <= {cfg.rsi_extreme_bull}")
            state.bull_extreme_visited = True
            state.bear_extreme_visited = False
            state.extreme_bar          = bar_idx

        if rsi_val >= cfg.rsi_extreme_bear:
            if not state.bear_extreme_visited:
                logger.info(f"[V2_STAGE_1A] BEAR EXTREME ZONE VISITED: RSI={rsi_val:.2f} >= {cfg.rsi_extreme_bear}")
            state.bear_extreme_visited = True
            state.bull_extreme_visited = False
            state.extreme_bar          = bar_idx

        # -- Stage 1B: RSI Break -----------------------------------------------
        prev_rsi = df['rsi'].iloc[i - 1] if i > 0 else rsi_val

        rsi_bull_break = (
            state.bull_extreme_visited
            and prev_rsi <= cfg.rsi_bull_break
            and rsi_val  >  cfg.rsi_bull_break
        )
        rsi_bear_break = (
            state.bear_extreme_visited
            and prev_rsi >= cfg.rsi_bear_break
            and rsi_val  <  cfg.rsi_bear_break
        )

        if rsi_bull_break:
            logger.info(f"[V2_STAGE_1B] BULL BREAK DETECTED: RSI={prev_rsi:.2f} → {rsi_val:.2f} (> {cfg.rsi_bull_break})")
            state.bull_break_bar       = bar_idx
            state.bull_extreme_visited = False
            # Cancel any active bear setup
            state.reset_bear()

        if rsi_bear_break:
            logger.info(f"[V2_STAGE_1B] BEAR BREAK DETECTED: RSI={prev_rsi:.2f} → {rsi_val:.2f} (< {cfg.rsi_bear_break})")
            state.bear_break_bar       = bar_idx
            state.bear_extreme_visited = False
            # Cancel any active bull setup
            state.reset_bull()

        # -- Stage 1C: RSI Retest ----------------------------------------------
        bull_retest_active = (
            state.bull_break_bar is not None
            and 0 < (bar_idx - state.bull_break_bar) <= cfg.rsi_retest_bars
            and (cfg.rsi_bull_break - cfg.rsi_retest_buffer)
                <= rsi_val
                <= (cfg.rsi_bull_break + cfg.rsi_retest_buffer)
        )
        bear_retest_active = (
            state.bear_break_bar is not None
            and 0 < (bar_idx - state.bear_break_bar) <= cfg.rsi_retest_bars
            and (cfg.rsi_bear_break - cfg.rsi_retest_buffer)
                <= rsi_val
                <= (cfg.rsi_bear_break + cfg.rsi_retest_buffer)
        )

        # Arm entry window on first retest bar
        if bull_retest_active and not state.bull_retest_done:
            logger.info(f"[V2_STAGE_1C] BULL RETEST DETECTED: RSI={rsi_val:.2f} in range [{cfg.rsi_bull_break - cfg.rsi_retest_buffer:.2f}, {cfg.rsi_bull_break + cfg.rsi_retest_buffer:.2f}]")
            state.bull_retest_done     = True
            state.bull_retest_bar      = bar_idx
            state.bull_entry_window_bar = bar_idx
            state.bull_entry_armed     = True
            logger.info(f"[V2_STAGE_2] BULL ENTRY WINDOW ARMED: Next {cfg.entry_window_bars} bars watch for EMA body break")

        if bear_retest_active and not state.bear_retest_done:
            logger.info(f"[V2_STAGE_1C] BEAR RETEST DETECTED: RSI={rsi_val:.2f} in range [{cfg.rsi_bear_break - cfg.rsi_retest_buffer:.2f}, {cfg.rsi_bear_break + cfg.rsi_retest_buffer:.2f}]")
            state.bear_retest_done     = True
            state.bear_retest_bar      = bar_idx
            state.bear_entry_window_bar = bar_idx
            state.bear_entry_armed     = True
            logger.info(f"[V2_STAGE_2] BEAR ENTRY WINDOW ARMED: Next {cfg.entry_window_bars} bars watch for EMA body break")

        # Expire retest window with no retest -> reset break
        if (state.bull_break_bar is not None
                and not state.bull_retest_done
                and (bar_idx - state.bull_break_bar) > cfg.rsi_retest_bars):
            logger.debug(f"[V2_EXPIRY] BULL RETEST EXPIRED: No retest in {cfg.rsi_retest_bars} bars, resetting breaklevel")
            state.bull_break_bar = None

        if (state.bear_break_bar is not None
                and not state.bear_retest_done
                and (bar_idx - state.bear_break_bar) > cfg.rsi_retest_bars):
            logger.debug(f"[V2_EXPIRY] BEAR RETEST EXPIRED: No retest in {cfg.rsi_retest_bars} bars, resetting break level")
            state.bear_break_bar = None

        # -- Stage 2: Entry Window ---------------------------------------------
        bull_window_open = (
            state.bull_entry_armed
            and state.bull_entry_window_bar is not None
            and (bar_idx - state.bull_entry_window_bar) <= cfg.entry_window_bars
        )
        bear_window_open = (
            state.bear_entry_armed
            and state.bear_entry_window_bar is not None
            and (bar_idx - state.bear_entry_window_bar) <= cfg.entry_window_bars
        )

        # Expire entry window -> full reset
        if (state.bull_entry_armed
                and state.bull_entry_window_bar is not None
                and (bar_idx - state.bull_entry_window_bar) > cfg.entry_window_bars):
            state.reset_bull()

        if (state.bear_entry_armed
                and state.bear_entry_window_bar is not None
                and (bar_idx - state.bear_entry_window_bar) > cfg.entry_window_bars):
            state.reset_bear()

        # -- Stage 2: Entry Trigger (DUAL-PATH CONFIRMATION) ----
        body_bull = _full_body_bull(row['open'], row['close'], ema_val)
        body_bear = _full_body_bear(row['open'], row['close'], ema_val)

        # Try MODE 1: Trend continuation (requires daily alignment)
        bull_trend_result = evaluate_trend_continuation(
            window_open=bull_window_open,
            body_valid=body_bull,
            daily_aligned=daily_bull,
            rsi_val=rsi_val,
            cfg=cfg
        )
        
        bear_trend_result = evaluate_trend_continuation(
            window_open=bear_window_open,
            body_valid=body_bear,
            daily_aligned=daily_bear,
            rsi_val=rsi_val,
            cfg=cfg
        )
        
        # Try MODE 2: Counter-trend sniper (activates when daily alignment fails)
        daily_failed = not (daily_bull or daily_bear)
        
        bull_counter_result = evaluate_counter_trend(
            window_open=bull_window_open,
            body_valid=body_bull,
            daily_failed=daily_failed,
            rsi_val=rsi_val,
            rsi_extreme=(rsi_val < 20.0),
            cfg=cfg
        )
        
        bear_counter_result = evaluate_counter_trend(
            window_open=bear_window_open,
            body_valid=body_bear,
            daily_failed=daily_failed,
            rsi_val=rsi_val,
            rsi_extreme=(rsi_val > 80.0),
            cfg=cfg
        )
        
        # Determine final signal based on approved confirmations
        long_confirmation = bull_trend_result if bull_trend_result.approved else bull_counter_result
        short_confirmation = bear_trend_result if bear_trend_result.approved else bear_counter_result
        
        long_condition = long_confirmation.approved
        short_condition = short_confirmation.approved
        
        confirmation_mode = None
        position_size_multiplier = 1.0

        # -- Compute SL / TP ---------------------------------------------------
        sl = np.nan
        tp = np.nan

        if long_condition and not np.isnan(last_swing_low):
            sl   = last_swing_low * (1 - cfg.sl_buffer_pct / 100)
            risk = row['close'] - sl
            tp   = row['close'] + (risk * cfg.rr_ratio) if risk > 0 else np.nan
            confirmation_mode = long_confirmation.mode
            position_size_multiplier = long_confirmation.position_size_multiplier

        if short_condition and not np.isnan(last_swing_high):
            sl   = last_swing_high * (1 + cfg.sl_buffer_pct / 100)
            risk = sl - row['close']
            tp   = row['close'] - (risk * cfg.rr_ratio) if risk > 0 else np.nan
            confirmation_mode = short_confirmation.mode
            position_size_multiplier = short_confirmation.position_size_multiplier

        # -- Determine signal --------------------------------------------------
        if long_condition:
            signal = Signal.BUY
            logger.info(
                f"[V2_SIGNAL_BUY] LONG ENTRY CONFIRMED via {confirmation_mode} "
                f"(pos_mult={position_size_multiplier:.1f}): "
                f"RSI={rsi_val:.2f} | EMA={ema_val:.6f} | Price={row['close']:.6f} | "
                f"SL={sl:.6f} | TP={tp:.6f}"
            )
            state.reset_bull()
        elif short_condition:
            signal = Signal.SELL
            logger.info(
                f"[V2_SIGNAL_SELL] SHORT ENTRY CONFIRMED via {confirmation_mode} "
                f"(pos_mult={position_size_multiplier:.1f}): "
                f"RSI={rsi_val:.2f} | EMA={ema_val:.6f} | Price={row['close']:.6f} | "
                f"SL={sl:.6f} | TP={tp:.6f}"
            )
            state.reset_bear()
        else:
            signal = Signal.NEUTRAL

        results.append({
            'signal':              int(signal),
            'stage':               state.stage_description,
            'rsi':                 round(rsi_val, 4),
            'ema_21':              round(ema_val, 6),
            'bull_extreme':        state.bull_extreme_visited,
            'bear_extreme':        state.bear_extreme_visited,
            'sl':                  sl,
            'tp':                  tp,
            'confirmation_mode':   confirmation_mode,
            'position_size_mult':  position_size_multiplier,
        })

    result_df = pd.DataFrame(results, index=df.index)
    return result_df


def _null_result(state: SequenceState) -> dict:
    return {
        'signal':              0,
        'stage':               state.stage_description,
        'rsi':                 np.nan,
        'ema_21':              np.nan,
        'bull_extreme':        False,
        'bear_extreme':        False,
        'sl':                  np.nan,
        'tp':                  np.nan,
        'confirmation_mode':   None,
        'position_size_mult':  1.0,
    }


# ===============================================================================
# LIVE EVALUATOR
# For production: stateful, called bar by bar with persisted state.
# One SignalEngine instance per (ticker, interval) pair.
# ===============================================================================

class SignalEngine:
    """
    Production signal engine for live trading.

    Usage:
        engine = SignalEngine(ticker='EURUSD', interval='1h')
        signal = engine.evaluate(df_ohlcv)
        # Returns Signal.BUY, Signal.SELL, or Signal.NEUTRAL

    State persists between calls. Feed each new closed bar as it arrives.
    Pass only the last N bars needed (max_bars_back=500 recommended).

    The engine is stateful by design. Do NOT share one engine instance
    across multiple tickers or intervals.
    """

    MIN_BARS = 120  # Hard gate: minimum bars before any signal is considered

    def __init__(
        self,
        ticker:   str,
        interval: str,
        config:   Optional[TimeframeConfig] = None,
        use_htf:  bool = True,
    ):
        self.ticker   = ticker
        self.interval = interval
        self.cfg      = config or get_timeframe_config(interval)
        self.use_htf  = use_htf
        self.state    = SequenceState()

        # Rolling swing points
        self._last_swing_high: float = np.nan
        self._last_swing_low:  float = np.nan
        
        # Dual-path confirmation tracking (populated by _process_bar)
        self._last_confirmation_result: Optional[ConfirmationResult] = None

    def evaluate(self, df_ohlcv: pd.DataFrame) -> Signal:
        from async_scheduler import log_stage_transition
        """
        Evaluate the latest bar and return signal.

        Args:
            df_ohlcv: DataFrame with [open, high, low, close] columns.
                      Index must be datetime. Pass last 500 bars for best results.
                      The LAST row is treated as the current bar.

        Returns:
            Signal.BUY     ->  1
            Signal.SELL    -> -1
            Signal.NEUTRAL ->  0
        """
        if df_ohlcv is None or len(df_ohlcv) < self.MIN_BARS:
            return Signal.NEUTRAL

        df       = df_ohlcv.copy()
        df['e21'] = _ema(df['close'], self.cfg.ema_period)
        df['rsi'] = _rsi(df['close'], self.cfg.rsi_period)

        # Update swing points from recent history
        ph_series = _pivot_high(df['high'], self.cfg.swing_lookback)
        pl_series = _pivot_low(df['low'],   self.cfg.swing_lookback)
        last_ph   = ph_series.dropna()
        last_pl   = pl_series.dropna()
        if len(last_ph) > 0:
            self._last_swing_high = last_ph.iloc[-1]
        if len(last_pl) > 0:
            self._last_swing_low  = last_pl.iloc[-1]

        curr     = df.iloc[-1]
        prev_rsi = df['rsi'].iloc[-2] if len(df) >= 2 else df['rsi'].iloc[-1]
        rsi_val  = curr['rsi']
        ema_val  = curr['e21']
        bar_idx  = len(df) - 1

        if pd.isna(rsi_val) or pd.isna(ema_val):
            return Signal.NEUTRAL

        # Daily alignment
        if self.use_htf:
            daily_bull, daily_bear = _get_daily_alignment(df, self.cfg.htf_ema_period)
        else:
            daily_bull, daily_bear = True, True

        # Run state machine on current bar
        return self._process_bar(
            bar_idx, rsi_val, prev_rsi, ema_val,
            curr['open'], curr['close'],
            daily_bull, daily_bear
        )

    def advance_state(
        self,
        df_ohlcv: pd.DataFrame,
        persisted_state: Optional[dict] = None,
        last_processed_bar_time: Optional[str] = None,
    ) -> tuple[Signal, dict, Optional['ConfirmationResult']]:
        """
        Advance state machine through new bars since last sweep.
        
        This is the stateful entry point for EventMonitor sweeps.
        Maintains full SequenceState across sweep boundaries.
        
        Args:
            df_ohlcv: DataFrame with [open, high, low, close] columns (datetime index)
            persisted_state: Previous SequenceState as dict (from database)
            last_processed_bar_time: ISO timestamp of last bar we processed
            
        Returns:
            (signal: Signal, updated_state_dict: dict, confirmation_result: ConfirmationResult)
                signal: -1 (SELL), 0 (NEUTRAL), 1 (BUY)
                updated_state_dict: Persisted SequenceState for next sweep
                confirmation_result: ConfirmationResult object with mode and position_size_multiplier
        """
        if df_ohlcv is None or len(df_ohlcv) < self.MIN_BARS:
            # Not enough bars - return current state unchanged
            return Signal.NEUTRAL, persisted_state or {}, None

        # Restore persisted state
        self.state = SequenceState.from_dict(persisted_state) if persisted_state else SequenceState()

        df = df_ohlcv.copy()
        df['e21'] = _ema(df['close'], self.cfg.ema_period)
        df['rsi'] = _rsi(df['close'], self.cfg.rsi_period)

        # Update swing points from recent history
        ph_series = _pivot_high(df['high'], self.cfg.swing_lookback)
        pl_series = _pivot_low(df['low'],   self.cfg.swing_lookback)
        last_ph   = ph_series.dropna()
        last_pl   = pl_series.dropna()
        if len(last_ph) > 0:
            self._last_swing_high = last_ph.iloc[-1]
        if len(last_pl) > 0:
            self._last_swing_low  = last_pl.iloc[-1]

        # Daily alignment (computed once for all bars)
        if self.use_htf:
            daily_bull, daily_bear = _get_daily_alignment(df, self.cfg.htf_ema_period)
        else:
            daily_bull, daily_bear = True, True

        # Determine which bars to process (only NEW bars since last sweep)
        start_idx = 0
        if last_processed_bar_time:
            try:
                last_time = pd.Timestamp(last_processed_bar_time)
                # Find first bar after last_processed_bar_time
                mask = df.index > last_time
                if mask.any():
                    start_idx = df.index.searchsorted(last_time, side='right')
                else:
                    # No new bars - return unchanged state
                    logger.debug(f"[V2_ADVANCE] {self.ticker}-{self.interval}: No new bars since {last_processed_bar_time}")
                    return Signal.NEUTRAL, self.state.to_dict(), None
            except Exception as e:
                logger.warning(f"[V2_ADVANCE] {self.ticker}-{self.interval}: Error parsing last_processed_bar_time: {e}")

        last_signal = Signal.NEUTRAL
        latest_bar_time = None

        # Process each new bar
        for i in range(start_idx, len(df)):
            row      = df.iloc[i]
            bar_idx  = i
            rsi_val  = row['rsi']
            ema_val  = row['e21']
            latest_bar_time = row.name  # Store timestamp of this bar

            if pd.isna(rsi_val) or pd.isna(ema_val):
                continue

            prev_rsi = df['rsi'].iloc[i - 1] if i > 0 else rsi_val

            # Run bar through state machine
            signal = self._process_bar(
                bar_idx, rsi_val, prev_rsi, ema_val,
                row['open'], row['close'],
                daily_bull, daily_bear
            )

            if signal != Signal.NEUTRAL:
                last_signal = signal
                # After signal, state resets in _process_bar
                logger.info(f"[V2_ADVANCE] {self.ticker}-{self.interval}: Signal {signal.name} at bar {i}")

        # Prepare updated state dict with timestamp of latest bar processed
        updated_state = self.state.to_dict()
        if latest_bar_time:
            updated_state['last_processed_bar_time'] = latest_bar_time.isoformat()

        logger.debug(f"[V2_ADVANCE] {self.ticker}-{self.interval}: Processed bars {start_idx}-{len(df)-1}, signal={last_signal.name}, stage={self.state.stage_description}")

        # Return signal, state, and last confirmation result (if signal was generated)
        last_confirmation = self._last_confirmation_result if last_signal != Signal.NEUTRAL else None
        return last_signal, updated_state, last_confirmation

    def _process_bar(
        self,
        bar_idx:    int,
        rsi_val:    float,
        prev_rsi:   float,
        ema_val:    float,
        bar_open:   float,
        bar_close:  float,
        daily_bull: bool,
        daily_bear: bool,
    ) -> Signal:
        s = self.state
        cfg = self.cfg

        # -- Stage 1A: Extreme zone --------------------------------------------
        if (bar_idx - s.extreme_bar) > cfg.rsi_extreme_reset:
            s.bull_extreme_visited = False
            s.bear_extreme_visited = False

        if rsi_val <= cfg.rsi_extreme_bull:
            s.bull_extreme_visited = True
            try:
                log_stage_transition(self.ticker, self.interval, "BULL", "NEUTRAL", "1A", bar_idx, None, float(rsi_val), notes="Extreme visited")
            except Exception: pass
            s.bear_extreme_visited = False
            s.extreme_bar          = bar_idx

        if rsi_val >= cfg.rsi_extreme_bear:
            s.bear_extreme_visited = True
            try:
                log_stage_transition(self.ticker, self.interval, "BEAR", "NEUTRAL", "1A", bar_idx, None, float(rsi_val), notes="Extreme visited")
            except Exception: pass
            s.bull_extreme_visited = False
            s.extreme_bar          = bar_idx

        # -- Stage 1B: Break ---------------------------------------------------
        rsi_bull_break = (
            s.bull_extreme_visited
            and prev_rsi <= cfg.rsi_bull_break
            and rsi_val  >  cfg.rsi_bull_break
        )
        rsi_bear_break = (
            s.bear_extreme_visited
            and prev_rsi >= cfg.rsi_bear_break
            and rsi_val  <  cfg.rsi_bear_break
        )

        if rsi_bull_break:
            s.bull_break_bar       = bar_idx
            try:
                log_stage_transition(self.ticker, self.interval, "BULL", "1A", "1B", bar_idx, None, float(rsi_val), notes="RSI break")
            except Exception: pass
            s.bull_extreme_visited = False
            s.reset_bear()

        if rsi_bear_break:
            s.bear_break_bar       = bar_idx
            try:
                log_stage_transition(self.ticker, self.interval, "BEAR", "1A", "1B", bar_idx, None, float(rsi_val), notes="RSI break")
            except Exception: pass
            s.bear_extreme_visited = False
            s.reset_bull()

        # -- Stage 1C: Retest --------------------------------------------------
        bull_retest_active = (
            s.bull_break_bar is not None
            and 0 < (bar_idx - s.bull_break_bar) <= cfg.rsi_retest_bars
            and (cfg.rsi_bull_break - cfg.rsi_retest_buffer)
                <= rsi_val
                <= (cfg.rsi_bull_break + cfg.rsi_retest_buffer)
        )
        bear_retest_active = (
            s.bear_break_bar is not None
            and 0 < (bar_idx - s.bear_break_bar) <= cfg.rsi_retest_bars
            and (cfg.rsi_bear_break - cfg.rsi_retest_buffer)
                <= rsi_val
                <= (cfg.rsi_bear_break + cfg.rsi_retest_buffer)
        )

        if bull_retest_active and not s.bull_retest_done:
            s.bull_retest_done      = True
            try:
                log_stage_transition(self.ticker, self.interval, "BULL", "1B", "1C", bar_idx, None, float(rsi_val), notes="Retest confirmed")
            except Exception: pass
            s.bull_retest_bar       = bar_idx
            s.bull_entry_window_bar = bar_idx
            s.bull_entry_armed      = True

        if bear_retest_active and not s.bear_retest_done:
            s.bear_retest_done      = True
            try:
                log_stage_transition(self.ticker, self.interval, "BEAR", "1B", "1C", bar_idx, None, float(rsi_val), notes="Retest confirmed")
            except Exception: pass
            s.bear_retest_bar       = bar_idx
            s.bear_entry_window_bar = bar_idx
            s.bear_entry_armed      = True

        # Expire retest window with no retest
        if (s.bull_break_bar is not None
                and not s.bull_retest_done
                and (bar_idx - s.bull_break_bar) > cfg.rsi_retest_bars):
            s.bull_break_bar = None

        if (s.bear_break_bar is not None
                and not s.bear_retest_done
                and (bar_idx - s.bear_break_bar) > cfg.rsi_retest_bars):
            s.bear_break_bar = None

        # -- Stage 2: Entry window ---------------------------------------------
        bull_window_open = (
            s.bull_entry_armed
            and s.bull_entry_window_bar is not None
            and (bar_idx - s.bull_entry_window_bar) <= cfg.entry_window_bars
        )
        bear_window_open = (
            s.bear_entry_armed
            and s.bear_entry_window_bar is not None
            and (bar_idx - s.bear_entry_window_bar) <= cfg.entry_window_bars
        )

        # Expire entry window -> full reset
        if (s.bull_entry_armed
                and s.bull_entry_window_bar is not None
                and (bar_idx - s.bull_entry_window_bar) > cfg.entry_window_bars):
            s.reset_bull()

        if (s.bear_entry_armed
                and s.bear_entry_window_bar is not None
                and (bar_idx - s.bear_entry_window_bar) > cfg.entry_window_bars):
            s.reset_bear()

        # -- Stage 2: Entry trigger (DUAL-PATH CONFIRMATION) ----
        body_bull = _full_body_bull(bar_open, bar_close, ema_val)
        body_bear = _full_body_bear(bar_open, bar_close, ema_val)

        # Try MODE 1: Trend continuation (requires daily alignment)
        bull_trend_result = evaluate_trend_continuation(
            window_open=bull_window_open,
            body_valid=body_bull,
            daily_aligned=daily_bull,
            rsi_val=rsi_val,
            cfg=self.cfg
        )
        
        bear_trend_result = evaluate_trend_continuation(
            window_open=bear_window_open,
            body_valid=body_bear,
            daily_aligned=daily_bear,
            rsi_val=rsi_val,
            cfg=self.cfg
        )
        
        # Try MODE 2: Counter-trend sniper (activates when daily alignment fails)
        # Note: daily_failed means BOTH daily_bull and daily_bear are False
        daily_failed = not (daily_bull or daily_bear)
        
        bull_counter_result = evaluate_counter_trend(
            window_open=bull_window_open,
            body_valid=body_bull,
            daily_failed=daily_failed,
            rsi_val=rsi_val,
            rsi_extreme=(rsi_val < 20.0),  # Very oversold for bull counter-trend
            cfg=self.cfg
        )
        
        bear_counter_result = evaluate_counter_trend(
            window_open=bear_window_open,
            body_valid=body_bear,
            daily_failed=daily_failed,
            rsi_val=rsi_val,
            rsi_extreme=(rsi_val > 80.0),  # Very overbought for bear counter-trend
            cfg=self.cfg
        )
        
        # Determine final signal based on approved confirmations
        long_signal_result = bull_trend_result if bull_trend_result.approved else bull_counter_result
        short_signal_result = bear_trend_result if bear_trend_result.approved else bear_counter_result
        
        # Store confirmation result for access by caller
        self._last_confirmation_result = long_signal_result if long_signal_result.approved else (
            short_signal_result if short_signal_result.approved else None
        )

        if long_signal_result.approved:
            logger.info(
                f"[V2_SIGNAL_EMIT] BUY CONFIRMED via {long_signal_result.mode} "
                f"(pos_multiplier={long_signal_result.position_size_multiplier:.1f}) | "
                f"{long_signal_result.reason}"
            )
            s.reset_bull()
            return Signal.BUY

        if short_signal_result.approved:
            logger.info(
                f"[V2_SIGNAL_EMIT] SELL CONFIRMED via {short_signal_result.mode} "
                f"(pos_multiplier={short_signal_result.position_size_multiplier:.1f}) | "
                f"{short_signal_result.reason}"
            )
            s.reset_bear()
            return Signal.SELL

        # Log Stage 2 armed status (no signal yet - waiting for confirmation)
        if bull_window_open:
            logger.debug(f"[V2_STAGE_2] BULL entry window open - waiting for EMA body break confirmation")
        if bear_window_open:
            logger.debug(f"[V2_STAGE_2] BEAR entry window open - waiting for EMA body break confirmation")

        return Signal.NEUTRAL

    @property
    def stage(self) -> str:
        return self.state.stage_description
    
    @property
    def last_confirmation(self) -> Optional[ConfirmationResult]:
        """Return the result of the most recent dual-path confirmation evaluation."""
        return self._last_confirmation_result

    def reset(self):
        """Hard reset state machine. Use when switching symbols or after gap."""
        self.state = SequenceState()
        self._last_confirmation_result = None


# ===============================================================================
# CONVENIENCE WRAPPER - drop-in replacement for original evaluate()
# ===============================================================================

def evaluate(
    ticker:    str,
    interval:  str,
    df_ohlcv:  pd.DataFrame,
    min_rows:  int = 120,
    use_htf:   bool = True,
) -> int:
    """
    Stateless convenience wrapper. Direct drop-in for the original evaluate().

    WARNING: This is stateless - it re-runs the full state machine on every call.
    For production live trading, use SignalEngine instead (persistent state).
    This wrapper is suitable for: one-off checks, testing, signal validation.

    Returns: 1 (BUY), -1 (SELL), 0 (NEUTRAL)
    """
    if df_ohlcv is None or len(df_ohlcv) < min_rows:
        logger.debug(f"[V2_EVALUATE] {ticker}-{interval}: MIN_ROWS gate. Rows={len(df_ohlcv) if df_ohlcv is not None else 0} < {min_rows}")
        return int(Signal.NEUTRAL)

    try:
        result_df = backtest(df_ohlcv, interval, use_htf=use_htf)
        last_signal = result_df['signal'].iloc[-1]
        logger.debug(f"[V2_EVALUATE] {ticker}-{interval}: Signal={last_signal} | Stage={result_df['stage'].iloc[-1]}")
        return int(last_signal)
    except Exception as e:
        logger.error(f"[V2_EVALUATE] {ticker}-{interval}: ERROR - {str(e)}")
        return int(Signal.NEUTRAL)

