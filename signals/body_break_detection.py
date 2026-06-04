"""Full body break detection module for engulfed structure signals.

This module detects when a candle's body (open-to-close) completely closes
outside a price range, indicating a potential structure breakout.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class BodyBreakEvent:
    """Represents detected full body break."""

    is_bullish_break: bool
    is_bearish_break: bool
    break_magnitude: float
    break_pips: float
    break_type: str  # "bullish" | "bearish" | "none"


def detect_full_body_break(
    df: pd.DataFrame,
    range_high: float,
    range_low: float,
    min_break_pips: float = 2.0,
) -> Optional[BodyBreakEvent]:
    """Detect if current candle breaks outside range with full body.

    A full body break means:
    - For BULLISH: candle closes above range_high, opened below it
    - For BEARISH: candle closes below range_low, opened above it

    Args:
        df: OHLCV price data.
        range_high: Upper boundary of range.
        range_low: Lower boundary of range.
        min_break_pips: Minimum pips break required (default 2).

    Returns:
        BodyBreakEvent describing the break, or None if no break detected.

    Example:
        >>> break_event = detect_full_body_break(df, 1.17620, 1.17580, min_break_pips=2)
        >>> if break_event and break_event.is_bullish_break:
        ...     print(f"Bullish break of {break_event.break_pips} pips")
    """

    if not isinstance(df, pd.DataFrame):
        return None
    if len(df) < 1:
        return None
    if not {"open", "close", "high", "low"}.issubset(df.columns):
        return None

    if range_high <= 0 or range_low <= 0:
        return None

    current_open = float(df["open"].iloc[-1])
    current_close = float(df["close"].iloc[-1])
    current_high = float(df["high"].iloc[-1])
    current_low = float(df["low"].iloc[-1])

    # Calculate pips based on current price level (approximation)
    # For forex: 1 pip typically = 0.0001 for most pairs (or 0.01 for JPY pairs)
    # Using generic calculation: pips = (price_diff / current_price) * 10000
    price_level = (range_high + range_low) / 2
    pips_scale = 10000 if price_level > 10 else 100

    # Bullish full body break
    bullish_break = (
        current_close > range_high
        and current_open < range_high
        and current_close > current_open
    )

    bullish_break_pips = (
        ((current_close - range_high) / range_high) * pips_scale
        if bullish_break
        else 0
    )

    # Bearish full body break
    bearish_break = (
        current_close < range_low
        and current_open > range_low
        and current_close < current_open
    )

    bearish_break_pips = (
        ((range_low - current_close) / range_low) * pips_scale
        if bearish_break
        else 0
    )

    # Check minimum break requirement
    if bullish_break and bullish_break_pips < min_break_pips:
        bullish_break = False

    if bearish_break and bearish_break_pips < min_break_pips:
        bearish_break = False

    # Determine break type
    if bullish_break:
        break_type = "bullish"
        break_magnitude = current_close - range_high
        break_pips = bullish_break_pips
    elif bearish_break:
        break_type = "bearish"
        break_magnitude = range_low - current_close
        break_pips = bearish_break_pips
    else:
        break_type = "none"
        break_magnitude = 0.0
        break_pips = 0.0

    return BodyBreakEvent(
        is_bullish_break=bullish_break,
        is_bearish_break=bearish_break,
        break_magnitude=break_magnitude,
        break_pips=break_pips,
        break_type=break_type,
    )
