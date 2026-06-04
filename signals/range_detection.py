"""Range identification module for engulfed structure detection.

This module identifies recent swing highs/lows (price ranges) that form
the basis for structure break signals. Used by engulfed_structure_events detector.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd


@dataclass
class PriceRange:
    """Represents identified price range structure."""

    range_high: float
    range_low: float
    range_size: float
    lookback_period: int


def identify_price_ranges(
    df: pd.DataFrame,
    lookback: int = 20,
) -> Optional[PriceRange]:
    """Identify recent swing highs and lows.

    Args:
        df: OHLCV price data indexed by timestamp.
        lookback: Number of candles to scan for highs/lows.

    Returns:
        PriceRange with identified structure, or None if insufficient data.

    Example:
        >>> ranges = identify_price_ranges(df, lookback=20)
        >>> if ranges:
        ...     print(f"Range: {ranges.range_low} - {ranges.range_high}")
    """

    if not isinstance(df, pd.DataFrame):
        return None
    if len(df) < lookback + 1:
        return None
    if not {"high", "low"}.issubset(df.columns):
        return None

    recent = df.tail(lookback + 1)
    
    # Exclude current candle to get reference range
    reference = recent.iloc[:-1]
    range_high = float(reference["high"].max())
    range_low = float(reference["low"].min())
    
    if range_high <= 0 or range_low <= 0:
        return None

    range_size = range_high - range_low

    return PriceRange(
        range_high=range_high,
        range_low=range_low,
        range_size=range_size,
        lookback_period=lookback,
    )
