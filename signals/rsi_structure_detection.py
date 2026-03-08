"""RSI structure detection module for confluent structure signals.

This module identifies when RSI breaks its own recent structure levels
or extreme zones, providing confluence with price structure breaks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class RSIStructure:
    """Represents RSI structure levels."""

    rsi_high_20: float
    rsi_low_20: float
    current_rsi: float
    broke_high: bool
    broke_low: bool
    broke_overbought: bool
    broke_oversold: bool
    structure_type: str  # "above_high" | "below_low" | "overbought" | "oversold" | "none"


def _calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI indicator."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(to_replace=0, value=np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def detect_rsi_structure_break(
    df: pd.DataFrame,
    period: int = 14,
    lookback_structure: int = 20,
    overbought_level: float = 70.0,
    oversold_level: float = 30.0,
) -> Optional[RSIStructure]:
    """Detect when RSI breaks its own structure levels.

    Checks for:
    1. RSI breaking above/below recent highs/lows (last 20 candles)
    2. RSI breaking overbought (>70) or oversold (<30) zones

    Args:
        df: OHLCV price data with close prices.
        period: RSI calculation period (default 14).
        lookback_structure: Candles to scan for RSI structure (default 20).
        overbought_level: RSI level for overbought (default 70).
        oversold_level: RSI level for oversold (default 30).

    Returns:
        RSIStructure with break information, or None if insufficient data.

    Example:
        >>> rsi_struct = detect_rsi_structure_break(df, period=14)
        >>> if rsi_struct and rsi_struct.broke_overbought:
        ...     print("RSI broke overbought level")
    """

    if not isinstance(df, pd.DataFrame):
        return None
    if not {"close"}.issubset(df.columns):
        return None
    if len(df) < max(period + 5, lookback_structure + 1):
        return None

    # Calculate RSI
    rsi_series = _calculate_rsi(df["close"], period=period)
    current_rsi = float(rsi_series.iloc[-1])

    if np.isnan(current_rsi):
        return None

    # Get RSI structure (exclude current candle)
    rsi_recent = rsi_series.tail(lookback_structure + 1)
    rsi_reference = rsi_recent.iloc[:-1]

    # Filter out NaN values
    rsi_reference = rsi_reference.dropna()
    if len(rsi_reference) < 5:
        return None

    rsi_high_20 = float(rsi_reference.max())
    rsi_low_20 = float(rsi_reference.min())

    # Check structure breaks
    broke_high = current_rsi > rsi_high_20
    broke_low = current_rsi < rsi_low_20

    # Check extreme zone breaks
    broke_overbought = current_rsi > overbought_level
    broke_oversold = current_rsi < oversold_level

    # Determine structure type
    if broke_high and broke_overbought:
        structure_type = "overbought"
    elif broke_low and broke_oversold:
        structure_type = "oversold"
    elif broke_high:
        structure_type = "above_high"
    elif broke_low:
        structure_type = "below_low"
    else:
        structure_type = "none"

    return RSIStructure(
        rsi_high_20=rsi_high_20,
        rsi_low_20=rsi_low_20,
        current_rsi=current_rsi,
        broke_high=broke_high,
        broke_low=broke_low,
        broke_overbought=broke_overbought,
        broke_oversold=broke_oversold,
        structure_type=structure_type,
    )
