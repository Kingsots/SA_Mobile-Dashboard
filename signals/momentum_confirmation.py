"""Momentum confirmation utilities for event-driven signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MomentumEvent:
    event_type: str
    confidence: float
    timestamp: pd.Timestamp
    details: Dict[str, Any]


def _validate(df: pd.DataFrame, min_length: int = 100) -> bool:
    if not isinstance(df, pd.DataFrame):
        return False
    if not {"close"}.issubset(df.columns):
        return False
    if len(df) < min_length:
        return False
    return True


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(to_replace=0, value=np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def detect_ema_crossover(
    df: pd.DataFrame,
    fast_span: int = 21,
    slow_span: int = 100,
    separation_threshold: float = 0.001,
) -> Optional[MomentumEvent]:
    """Detect EMA crossovers between fast and slow moving averages."""

    if not _validate(df, min_length=slow_span + 5):
        return None

    closes = df["close"]
    fast = _ema(closes, fast_span)
    slow = _ema(closes, slow_span)

    fast_tail = fast.tail(3)
    slow_tail = slow.tail(3)
    if fast_tail.isna().any() or slow_tail.isna().any():
        return None

    prev_fast, last_fast = fast_tail.iloc[-2:]
    prev_slow, last_slow = slow_tail.iloc[-2:]

    crossed_up = prev_fast < prev_slow and last_fast > last_slow
    crossed_down = prev_fast > prev_slow and last_fast < last_slow

    if not (crossed_up or crossed_down):
        return None

    separation = abs(last_fast - last_slow) / max(last_slow, 1e-9)
    if separation < separation_threshold:
        return None

    event_type = "ema_cross_bullish" if crossed_up else "ema_cross_bearish"
    confidence = float(np.clip(separation / separation_threshold * 0.5, 0.4, 0.9))

    return MomentumEvent(
        event_type=event_type,
        confidence=confidence,
        timestamp=pd.Timestamp(df.index[-1]),
        details={
            "fast": float(last_fast),
            "slow": float(last_slow),
            "separation": float(separation),
            "fast_span": fast_span,
            "slow_span": slow_span,
        },
    )


def detect_rsi_shift(
    df: pd.DataFrame,
    period: int = 14,
    overbought: float = 70.0,
    oversold: float = 30.0,
    rebound_threshold: float = 5.0,
) -> Optional[MomentumEvent]:
    """Detect RSI reversals from extreme zones."""

    if not _validate(df, min_length=period + 5):
        return None

    rsi = _rsi(df["close"], period=period)
    rsi_tail = rsi.tail(3)
    if rsi_tail.isna().any():
        return None

    prev, last = rsi_tail.iloc[-2:]
    timestamp = df.index[-1]

    # Bullish rebound: RSI emerging from oversold
    if prev < oversold and last > prev + rebound_threshold:
        confidence = float(np.clip((oversold - prev) / oversold + 0.5, 0.4, 0.9))
        return MomentumEvent(
            event_type="rsi_rebound_bullish",
            confidence=confidence,
            timestamp=pd.Timestamp(timestamp),
            details={
                "prev_rsi": float(prev),
                "current_rsi": float(last),
                "period": period,
            },
        )

    # Bearish rejection: RSI falling from overbought
    if prev > overbought and last < prev - rebound_threshold:
        confidence = float(np.clip((prev - overbought) / overbought + 0.5, 0.4, 0.9))
        return MomentumEvent(
            event_type="rsi_rejection_bearish",
            confidence=confidence,
            timestamp=pd.Timestamp(timestamp),
            details={
                "prev_rsi": float(prev),
                "current_rsi": float(last),
                "period": period,
            },
        )

    return None


def summarize_momentum(
    df: pd.DataFrame,
    fast_span: int = 21,
    slow_span: int = 100,
    period: int = 14,
) -> Tuple[float, float, float]:
    """Return the latest fast EMA, slow EMA, and RSI values."""

    if not _validate(df, min_length=slow_span + period):
        raise ValueError("Insufficient data for momentum summary")

    closes = df["close"]
    fast = _ema(closes, fast_span).iloc[-1]
    slow = _ema(closes, slow_span).iloc[-1]
    rsi = _rsi(closes, period=period).iloc[-1]
    return float(fast), float(slow), float(rsi)
