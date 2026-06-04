"""Volume and volatility detectors for event-driven signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class VolumeVolatilityEvent:
    event_type: str
    confidence: float
    timestamp: pd.Timestamp
    details: Dict[str, Any]


def _validate(df: pd.DataFrame, min_length: int = 30) -> bool:
    required = {"high", "low", "close", "volume"}
    if not isinstance(df, pd.DataFrame):
        return False
    if not required.issubset(df.columns):
        return False
    if len(df) < min_length:
        return False
    return True


def _true_range(df: pd.DataFrame) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = np.abs(df["high"] - df["close"].shift(1))
    low_close = np.abs(df["low"] - df["close"].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tr = _true_range(df)
    atr = tr.rolling(window=period, min_periods=period).mean()
    return atr


def detect_volume_spike(
    df: pd.DataFrame,
    window: int = 20,
    ratio_threshold: float = 1.5,
) -> Optional[VolumeVolatilityEvent]:
    """Detect abnormal volume expansion relative to rolling average."""

    if not _validate(df, min_length=max(window + 1, 30)):
        return None

    recent = df.tail(window + 1)
    avg_volume = recent["volume"].iloc[:-1].mean()
    current_volume = recent["volume"].iloc[-1]

    if avg_volume <= 0:
        return None

    ratio = current_volume / avg_volume
    if ratio < ratio_threshold:
        return None

    confidence = float(np.clip((ratio - ratio_threshold) / ratio_threshold + 0.5, 0.3, 0.95))
    return VolumeVolatilityEvent(
        event_type="volume_spike",
        confidence=confidence,
        timestamp=pd.Timestamp(recent.index[-1]),
        details={
            "current_volume": float(current_volume),
            "average_volume": float(avg_volume),
            "ratio": float(ratio),
            "window": window,
        },
    )


def detect_atr_expansion(
    df: pd.DataFrame,
    period: int = 14,
    expansion_ratio: float = 1.3,
) -> Optional[VolumeVolatilityEvent]:
    """Detect significant ATR expansion compared to historical ATR."""

    if not _validate(df, min_length=period * 4):
        return None

    atr_series = _atr(df, period=period)
    if atr_series.isna().all():
        return None

    recent_atr = atr_series.iloc[-1]
    baseline = atr_series.iloc[-period:-1].mean()

    if not np.isfinite(recent_atr) or not np.isfinite(baseline) or baseline <= 0:
        return None

    ratio = recent_atr / baseline
    if ratio < expansion_ratio:
        return None

    confidence = float(np.clip((ratio - expansion_ratio) / expansion_ratio + 0.5, 0.3, 0.9))
    return VolumeVolatilityEvent(
        event_type="volatility_expansion",
        confidence=confidence,
        timestamp=pd.Timestamp(df.index[-1]),
        details={
            "recent_atr": float(recent_atr),
            "baseline_atr": float(baseline),
            "ratio": float(ratio),
            "period": period,
        },
    )
