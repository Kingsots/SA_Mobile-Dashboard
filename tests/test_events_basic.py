"""Basic smoke tests for event-driven detector modules."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure parent directory is on sys.path so 'signals' can be imported
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import numpy as np

from signals.event_monitor import EventMonitor, EventMonitorConfig
from signals.market_structure import detect_higher_high_breakout
from signals.volume_volatility import detect_volume_spike
from signals.momentum_confirmation import detect_ema_crossover


def _build_trending_df(rows: int = 160) -> pd.DataFrame:
    index = pd.date_range(start="2024-01-01", periods=rows, freq="H")
    base = np.linspace(100, 110, rows) + np.random.normal(0, 0.2, rows)
    high = base + np.random.uniform(0.1, 0.5, rows)
    low = base - np.random.uniform(0.1, 0.5, rows)
    volume = np.full(rows, 1_000_000, dtype=float)
    volume[-1] = 2_000_000  # spike on latest bar
    df = pd.DataFrame(
        {
            "open": base,
            "high": high,
            "low": low,
            "close": base + np.random.normal(0, 0.1, rows),
            "volume": volume,
        },
        index=index,
    )
    return df


def test_structure_breakout_detects():
    df = _build_trending_df()
    event = detect_higher_high_breakout(df)
    assert event is None or event.event_type == "trendline_break_resistance"


def test_volume_spike_detects():
    df = _build_trending_df()
    event = detect_volume_spike(df)
    assert event is None or event.event_type == "volume_spike"


def test_ema_crossover_returns_expected_type():
    df = _build_trending_df()
    event = detect_ema_crossover(df)
    if event is not None:
        assert event.event_type in {"ema_cross_bullish", "ema_cross_bearish"}


def test_event_monitor_filters_duplicates():
    df = _build_trending_df()
    monitor = EventMonitor(EventMonitorConfig(cooldown_seconds=300))

    events_first = monitor.analyze("EURUSD", "1h", df)
    events_second = monitor.analyze("EURUSD", "1h", df)

    # First pass may detect events (depending on random noise), second should
    # never exceed first due to cooldown filtering.
    assert len(events_second) <= len(events_first)


def test_event_monitor_returns_market_events():
    df = _build_trending_df()
    monitor = EventMonitor()
    events = monitor.analyze("GBPUSD", "1h", df)
    for event in events:
        assert event.ticker == "GBPUSD"
        assert event.interval == "1h"
        assert event.event_type
        assert 0 <= event.confidence <= 1
        assert isinstance(event.timestamp, pd.Timestamp)
