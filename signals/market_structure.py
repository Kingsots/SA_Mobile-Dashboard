"""Market structure detectors for event-driven signals.

This module provides lightweight utilities to identify simple
price structure shifts such as higher-high breakouts and
lower-low breakdowns. Functions accept a pandas DataFrame with
`open`, `high`, `low`, `close` columns indexed by timestamp and
return metadata dictionaries describing detected events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class StructureEvent:
    """Represents a detected market-structure inflection."""

    event_type: str
    confidence: float
    timestamp: pd.Timestamp
    details: Dict[str, Any]


def _validate_input(df: pd.DataFrame, min_length: int = 10) -> bool:
    """Return True if DataFrame is usable for structure analysis."""

    required_cols = {"high", "low", "close"}
    if not isinstance(df, pd.DataFrame):
        return False
    if not required_cols.issubset(df.columns):
        return False
    if len(df) < min_length:
        return False
    return True


def detect_higher_high_breakout(
    df: pd.DataFrame,
    lookback: int = 20,
    min_break_ratio: float = 0.0015,
) -> Optional[StructureEvent]:
    """Detect a higher-high breakout relative to recent structure.

    Args:
        df: Price history indexed by timestamp.
        lookback: Number of previous candles to use for reference high.
        min_break_ratio: Minimal percentage break above the reference high.

    Returns:
        StructureEvent if breakout detected, otherwise ``None``.
    """

    if not _validate_input(df, min_length=max(lookback + 2, 10)):
        return None

    recent = df.tail(lookback + 1)
    reference_high = recent["high"].iloc[:-1].max()
    latest_high = recent["high"].iloc[-1]

    if reference_high == 0:
        return None

    breakout_ratio = (latest_high - reference_high) / reference_high
    if breakout_ratio <= min_break_ratio:
        return None

    confidence = float(np.clip(breakout_ratio / (min_break_ratio * 2.0), 0.2, 0.95))
    timestamp = recent.index[-1]

    return StructureEvent(
        event_type="trendline_break_resistance",
        confidence=confidence,
        timestamp=pd.Timestamp(timestamp),
        details={
            "reference_high": float(reference_high),
            "latest_high": float(latest_high),
            "breakout_ratio": float(breakout_ratio),
            "lookback": lookback,
        },
    )


def detect_lower_low_breakdown(
    df: pd.DataFrame,
    lookback: int = 20,
    min_break_ratio: float = 0.0015,
) -> Optional[StructureEvent]:
    """Detect a lower-low breakdown relative to recent structure."""

    if not _validate_input(df, min_length=max(lookback + 2, 10)):
        return None

    recent = df.tail(lookback + 1)
    reference_low = recent["low"].iloc[:-1].min()
    latest_low = recent["low"].iloc[-1]

    if reference_low == 0:
        return None

    breakdown_ratio = (reference_low - latest_low) / reference_low
    if breakdown_ratio <= min_break_ratio:
        return None

    confidence = float(np.clip(breakdown_ratio / (min_break_ratio * 2.0), 0.2, 0.95))
    timestamp = recent.index[-1]

    return StructureEvent(
        event_type="trendline_break_support",
        confidence=confidence,
        timestamp=pd.Timestamp(timestamp),
        details={
            "reference_low": float(reference_low),
            "latest_low": float(latest_low),
            "breakdown_ratio": float(breakdown_ratio),
            "lookback": lookback,
        },
    )


def detect_structure_shift(
    df: pd.DataFrame,
    swing_window: int = 5,
    tolerance: float = 0.0005,
) -> Optional[StructureEvent]:
    """Detects a basic structure shift via higher highs and higher lows.

    The detector looks for consecutive higher highs and higher lows (bullish)
    or lower highs and lower lows (bearish) comparing the last three swing points.
    """

    if not _validate_input(df, min_length=swing_window * 3):
        return None

    window = df.tail(swing_window * 3)
    highs = window["high"].rolling(window=swing_window).max().dropna().tail(3)
    lows = window["low"].rolling(window=swing_window).min().dropna().tail(3)

    if len(highs) < 3 or len(lows) < 3:
        return None

    latest_time = window.index[-1]

    hh = highs.iloc[-3:]  # ensure order preserved
    ll = lows.iloc[-3:]

    bullish = hh.is_monotonic_increasing and ll.is_monotonic_increasing
    bearish = hh.is_monotonic_decreasing and ll.is_monotonic_decreasing

    if bullish and (hh.iloc[-1] - hh.iloc[0]) / max(hh.iloc[0], 1e-9) > tolerance:
        confidence = float(np.clip((hh.iloc[-1] - hh.iloc[-2]) / max(hh.iloc[-2], 1e-9), 0.1, 0.9))
        return StructureEvent(
            event_type="structure_higher_highs",
            confidence=confidence,
            timestamp=pd.Timestamp(latest_time),
            details={
                "highs": [float(x) for x in hh.tolist()],
                "lows": [float(x) for x in ll.tolist()],
            },
        )

    if bearish and (ll.iloc[0] - ll.iloc[-1]) / max(ll.iloc[0], 1e-9) > tolerance:
        confidence = float(np.clip((ll.iloc[-2] - ll.iloc[-1]) / max(ll.iloc[-2], 1e-9), 0.1, 0.9))
        return StructureEvent(
            event_type="structure_lower_lows",
            confidence=confidence,
            timestamp=pd.Timestamp(latest_time),
            details={
                "highs": [float(x) for x in hh.tolist()],
                "lows": [float(x) for x in ll.tolist()],
            },
        )

    return None
