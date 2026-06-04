"""Event filtering utilities for the event-driven signal engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd


@dataclass(frozen=True)
class MarketEvent:
    """Canonical representation of a detected market event."""

    ticker: str
    interval: str
    event_type: str
    confidence: float
    timestamp: pd.Timestamp
    details: Dict[str, Any] = field(default_factory=dict)

    def key(self) -> Tuple[str, str, str]:
        return self.ticker, self.interval, self.event_type

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "ticker": self.ticker,
            "interval": self.interval,
            "event_type": self.event_type,
            "confidence": float(self.confidence),
            "timestamp": pd.Timestamp(self.timestamp).isoformat(),
        }
        if self.details:
            data["details"] = self.details
        return data


class EventFilter:
    """Applies deduplication, confidence checks and cooldown windows."""

    def __init__(
        self,
        min_confidence: float = 0.55,
        cooldown_seconds: int = 3600,
    ) -> None:
        if min_confidence < 0 or min_confidence > 1:
            raise ValueError("min_confidence must be within [0, 1]")
        self.min_confidence = min_confidence
        self.cooldown = timedelta(seconds=cooldown_seconds)
        self._last_seen: Dict[Tuple[str, str, str], pd.Timestamp] = {}
        # Track last signal direction per (ticker, interval) for reversal detection
        self._last_direction: Dict[Tuple[str, str], str] = {}  # 'LONG' or 'SHORT'
        self._last_direction_timestamp: Dict[Tuple[str, str], pd.Timestamp] = {}

    def _get_signal_direction(self, event: MarketEvent) -> Optional[str]:
        """Infer signal direction from event type."""
        if "bullish" in event.event_type.lower():
            return "LONG"
        elif "bearish" in event.event_type.lower():
            return "SHORT"
        return None

    def is_valid(self, event: MarketEvent, now: Optional[pd.Timestamp] = None) -> bool:
        """Return True if event passes confidence and cooldown checks."""

        if event.confidence < self.min_confidence:
            return False

        now_ts = pd.Timestamp(now) if now is not None else event.timestamp
        
        # Check standard cooldown (per event type)
        last = self._last_seen.get(event.key())
        if last is not None:
            delta = now_ts - last
            if delta < self.cooldown:
                return False
        
        # Check for trend reversal (direction contradicts last signal on this pair)
        ticker_interval = (event.ticker, event.interval)
        signal_direction = self._get_signal_direction(event)
        
        if signal_direction is not None and ticker_interval in self._last_direction:
            last_direction = self._last_direction[ticker_interval]
            last_time = self._last_direction_timestamp[ticker_interval]
            
            # If direction contradicts last signal AND less than cooldown has passed,
            # require higher confidence to allow reversal
            time_since_last = now_ts - last_time
            if signal_direction != last_direction and time_since_last < self.cooldown:
                # Require at least 10% higher confidence for reversal signals
                reversal_threshold = self.min_confidence + 0.10
                if event.confidence < reversal_threshold:
                    return False
        
        return True

    def register(self, event: MarketEvent, now: Optional[pd.Timestamp] = None) -> None:
        """Record an event occurrence to enforce future cooldowns."""

        now_ts = pd.Timestamp(now) if now is not None else event.timestamp
        self._last_seen[event.key()] = now_ts
        
        # Track signal direction for reversal detection
        signal_direction = self._get_signal_direction(event)
        if signal_direction is not None:
            ticker_interval = (event.ticker, event.interval)
            self._last_direction[ticker_interval] = signal_direction
            self._last_direction_timestamp[ticker_interval] = now_ts

    def filter_events(self, events: Iterable[MarketEvent]) -> List[MarketEvent]:
        """Filter an iterable of events returning those that pass policies."""

        accepted: List[MarketEvent] = []
        now_ts = pd.Timestamp(datetime.now(timezone.utc))
        for event in events:
            if self.is_valid(event, now=now_ts):
                self.register(event, now=now_ts)
                accepted.append(event)
        return accepted

    def clear(self, ticker: Optional[str] = None) -> None:
        """Clear cooldowns optionally scoped to a ticker."""

        if ticker is None:
            self._last_seen.clear()
            self._last_direction.clear()
            self._last_direction_timestamp.clear()
            return

        keys_to_delete = [key for key in self._last_seen if key[0] == ticker]
        for key in keys_to_delete:
            del self._last_seen[key]
        
        # Also clear direction tracking for this ticker
        direction_keys_to_delete = [key for key in self._last_direction if key[0] == ticker]
        for key in direction_keys_to_delete:
            del self._last_direction[key]
            del self._last_direction_timestamp[key]

    def stats(self) -> Dict[str, Any]:
        """Return diagnostic information about the filter state."""

        return {
            "entries": len(self._last_seen),
            "direction_tracking": len(self._last_direction),
            "min_confidence": self.min_confidence,
            "cooldown_seconds": int(self.cooldown.total_seconds()),
        }
