"""Event monitor orchestrating detector modules for event-driven signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

import pandas as pd

from .event_filter import EventFilter, MarketEvent
from .market_structure import (
    StructureEvent,
    detect_higher_high_breakout,
    detect_lower_low_breakdown,
    detect_structure_shift,
)
from .momentum_confirmation import (
    MomentumEvent,
    detect_ema_crossover,
    detect_rsi_shift,
)
from .volume_volatility import (
    VolumeVolatilityEvent,
    detect_atr_expansion,
    detect_volume_spike,
)
from .range_detection import identify_price_ranges
from .body_break_detection import detect_full_body_break
from .rsi_structure_detection import detect_rsi_structure_break


@dataclass
class EventMonitorConfig:
    """Configuration bundle for the market event monitor."""

    min_confidence: float = 0.50  # Relaxed from 0.55 to catch more events
    cooldown_seconds: int = 3600
    structure_lookback: int = 20
    volume_window: int = 20
    atr_period: int = 14
    ema_fast: int = 21
    ema_slow: int = 100
    rsi_period: int = 14
    min_breakout_ratio: float = 0.0005  # 0.05% for forex 1h candles (was 0.15%)
    
    # Engulfed structure parameters
    engulfed_range_lookback: int = 20
    engulfed_min_break_pips: float = 2.0
    engulfed_min_volume_mult: float = 1.2
    engulfed_use_daily_filter: bool = False  # Optional multi-timeframe


class EventMonitor:
    """Combines detector modules and applies event filtering logic."""

    def __init__(self, config: Optional[EventMonitorConfig] = None) -> None:
        self.config = config or EventMonitorConfig()
        self.filter = EventFilter(
            min_confidence=self.config.min_confidence,
            cooldown_seconds=self.config.cooldown_seconds,
        )

    def _structure_events(self, df: pd.DataFrame) -> List[StructureEvent]:
        events: List[StructureEvent] = []
        event = detect_higher_high_breakout(df, lookback=self.config.structure_lookback, min_break_ratio=self.config.min_breakout_ratio)
        if event:
            events.append(event)
        event = detect_lower_low_breakdown(df, lookback=self.config.structure_lookback, min_break_ratio=self.config.min_breakout_ratio)
        if event:
            events.append(event)
        event = detect_structure_shift(df)
        if event:
            events.append(event)
        return events

    def _volume_events(self, df: pd.DataFrame) -> List[VolumeVolatilityEvent]:
        events: List[VolumeVolatilityEvent] = []
        event = detect_volume_spike(df, window=self.config.volume_window)
        if event:
            events.append(event)
        event = detect_atr_expansion(df, period=self.config.atr_period)
        if event:
            events.append(event)
        return events

    def _momentum_events(self, df: pd.DataFrame) -> List[MomentumEvent]:
        events: List[MomentumEvent] = []
        event = detect_ema_crossover(
            df,
            fast_span=self.config.ema_fast,
            slow_span=self.config.ema_slow,
        )
        if event:
            events.append(event)
        event = detect_rsi_shift(df, period=self.config.rsi_period)
        if event:
            events.append(event)
        return events

    def _engulfed_structure_events(self, df: pd.DataFrame) -> List[StructureEvent]:
        """Detect engulfed structure breaks with RSI confluence.
        
        Combines:
        - Price range identification (recent highs/lows)
        - Full body break detection (close outside range)
        - RSI structure break (RSI breaks 70/30 or recent structure)
        - Volume confirmation (volume > 1.2x average)
        """
        events: List[StructureEvent] = []
        
        if df is None or len(df) < self.config.engulfed_range_lookback + 5:
            return events
        
        # Step 1: Identify price range
        price_range = identify_price_ranges(
            df,
            lookback=self.config.engulfed_range_lookback,
        )
        if not price_range:
            return events
        
        # Step 2: Check for full body break
        body_break = detect_full_body_break(
            df,
            range_high=price_range.range_high,
            range_low=price_range.range_low,
            min_break_pips=self.config.engulfed_min_break_pips,
        )
        if not body_break or body_break.break_type == "none":
            return events
        
        # Step 3: Check RSI structure break
        rsi_structure = detect_rsi_structure_break(
            df,
            period=self.config.rsi_period,
            lookback_structure=self.config.engulfed_range_lookback,
        )
        if not rsi_structure or rsi_structure.structure_type == "none":
            return events
        
        # Step 4: Check for volume confirmation (optional - forex may not have volume data)
        recent_volume = df['volume'].tail(21)
        if len(recent_volume) < 20:
            return events
        avg_volume = recent_volume.iloc[:-1].mean()
        current_volume = recent_volume.iloc[-1]
        
        # Skip volume check if no volume data available (forex pairs from Tiingo)
        has_volume = avg_volume > 0 and current_volume > 0
        if has_volume and current_volume < avg_volume * self.config.engulfed_min_volume_mult:
            return events
        
        # Step 5: Check RSI and price alignment
        # For bullish break: body_break.is_bullish_break AND (rsi.broke_high OR rsi.broke_overbought)
        # For bearish break: body_break.is_bearish_break AND (rsi.broke_low OR rsi.broke_oversold)
        
        is_valid_bullish = (
            body_break.is_bullish_break
            and (rsi_structure.broke_high or rsi_structure.broke_overbought)
        )
        is_valid_bearish = (
            body_break.is_bearish_break
            and (rsi_structure.broke_low or rsi_structure.broke_oversold)
        )
        
        if not (is_valid_bullish or is_valid_bearish):
            return events
        
        # Calculate confluence confidence
        # Base: 0.50 + 0.15 (break) + 0.15 (RSI) + 0.10 (volume) = 0.90 max
        confidence = 0.50
        confidence += 0.15  # Full body break confirmed
        confidence += 0.15  # RSI structure aligned
        confidence += 0.10  # Volume spike confirmed
        confidence = min(confidence, 0.95)
        
        # Create event
        if is_valid_bullish:
            event_type = "engulfed_structure_bullish"
            details = {
                "range_high": price_range.range_high,
                "range_low": price_range.range_low,
                "range_size": price_range.range_size,
                "break_pips": body_break.break_pips,
                "break_magnitude": body_break.break_magnitude,
                "rsi_current": rsi_structure.current_rsi,
                "rsi_high_20": rsi_structure.rsi_high_20,
                "rsi_structure_type": rsi_structure.structure_type,
                "volume_ratio": current_volume / avg_volume if avg_volume > 0 else 0,
            }
        else:
            event_type = "engulfed_structure_bearish"
            details = {
                "range_high": price_range.range_high,
                "range_low": price_range.range_low,
                "range_size": price_range.range_size,
                "break_pips": body_break.break_pips,
                "break_magnitude": body_break.break_magnitude,
                "rsi_current": rsi_structure.current_rsi,
                "rsi_low_20": rsi_structure.rsi_low_20,
                "rsi_structure_type": rsi_structure.structure_type,
                "volume_ratio": current_volume / avg_volume if avg_volume > 0 else 0,
            }
        
        event = StructureEvent(
            event_type=event_type,
            confidence=confidence,
            timestamp=df.index[-1],
            details=details,
        )
        events.append(event)
        
        return events

    def _as_market_event(
        self,
        ticker: str,
        interval: str,
        raw_event: StructureEvent | VolumeVolatilityEvent | MomentumEvent,
    ) -> MarketEvent:
        return MarketEvent(
            ticker=ticker,
            interval=interval,
            event_type=raw_event.event_type,
            confidence=raw_event.confidence,
            timestamp=raw_event.timestamp,
            details=raw_event.details,
        )

    def analyze(
        self,
        ticker: str,
        interval: str,
        df: pd.DataFrame,
        lower_timeframe_dfs: Optional[dict] = None,
    ) -> List[MarketEvent]:
        """Run detectors and return filtered market events.
        
        Args:
            ticker: Trading symbol
            interval: Timeframe interval (e.g., '4h', '1h', '30m')
            df: OHLCV data for this timeframe
            lower_timeframe_dfs: Optional dict of lower timeframe DataFrames for multi-timeframe confirmation
                                e.g., {'30m': df_30m, '1h': df_1h} when analyzing 4h
        """

        if df is None or df.empty:
            return []

        raw_events: List[MarketEvent] = []

        # Existing detectors
        for event in self._structure_events(df):
            raw_events.append(self._as_market_event(ticker, interval, event))

        for event in self._volume_events(df):
            raw_events.append(self._as_market_event(ticker, interval, event))

        for event in self._momentum_events(df):
            raw_events.append(self._as_market_event(ticker, interval, event))

        # NEW: Engulfed structure detector
        for event in self._engulfed_structure_events(df):
            raw_events.append(self._as_market_event(ticker, interval, event))

        if not raw_events:
            return []

        # Apply multi-timeframe confirmation if provided
        filtered_events = self.filter.filter_events(raw_events)
        if lower_timeframe_dfs and interval in ['4h', '2h', '1h']:
            filtered_events = self._apply_multitimeframe_confirmation(
                filtered_events, 
                interval, 
                lower_timeframe_dfs
            )
        
        return filtered_events

    def _apply_multitimeframe_confirmation(
        self,
        events: List[MarketEvent],
        current_interval: str,
        lower_timeframe_dfs: dict,
    ) -> List[MarketEvent]:
        """Filter events based on multi-timeframe confirmation.
        
        Before accepting a 4h/2h/1h signal, verify that at least one lower timeframe
        (30m/1h as appropriate) shows alignment in the same direction.
        
        This prevents repeated signals when market reverses.
        """
        if not events:
            return events
        
        confirmed_events = []
        
        # Map current interval to required confirmation timeframes
        confirmation_map = {
            '4h': ['1h', '30m'],  # 4h needs 1h or 30m alignment
            '2h': ['1h', '30m'],  # 2h needs 1h or 30m alignment
            '1h': ['30m'],         # 1h needs 30m alignment
        }
        
        if current_interval not in confirmation_map:
            return events
        
        required_confirmations = confirmation_map[current_interval]
        
        for event in events:
            signal_direction = self._get_signal_direction_from_event(event)
            if signal_direction is None:
                # Not a directional event, pass through
                confirmed_events.append(event)
                continue
            
            # Check if any lower timeframe confirms this signal
            has_confirmation = False
            for lower_tf in required_confirmations:
                if lower_tf not in lower_timeframe_dfs:
                    continue
                
                lower_df = lower_timeframe_dfs[lower_tf]
                if lower_df is None or lower_df.empty:
                    continue
                
                # Check if lower timeframe has events in the same direction
                if self._check_timeframe_alignment(lower_df, signal_direction):
                    has_confirmation = True
                    break
            
            # Only add event if it has lower timeframe confirmation
            if has_confirmation:
                confirmed_events.append(event)
        
        return confirmed_events
    
    def _get_signal_direction_from_event(self, event: MarketEvent) -> Optional[str]:
        """Extract signal direction from market event."""
        if "bullish" in event.event_type.lower():
            return "LONG"
        elif "bearish" in event.event_type.lower():
            return "SHORT"
        return None
    
    def _check_timeframe_alignment(self, df: pd.DataFrame, direction: str) -> bool:
        """Check if a timeframe's recent data aligns with expected direction.
        
        For LONG: Check if EMA 21 > EMA 100 or price is above recent support
        For SHORT: Check if EMA 21 < EMA 100 or price is below recent resistance
        """
        if df is None or len(df) < max(self.config.ema_slow, self.config.structure_lookback) + 5:
            return False
        
        try:
            # Calculate EMAs
            ema_fast = df['close'].ewm(span=self.config.ema_fast, adjust=False).mean()
            ema_slow = df['close'].ewm(span=self.config.ema_slow, adjust=False).mean()
            
            current_ema_fast = ema_fast.iloc[-1]
            current_ema_slow = ema_slow.iloc[-1]
            current_price = df['close'].iloc[-1]
            
            if direction == "LONG":
                # Alignment: EMA fast above slow AND price above both
                return (current_ema_fast > current_ema_slow and 
                       current_price > current_ema_slow)
            else:  # SHORT
                # Alignment: EMA fast below slow AND price below both
                return (current_ema_fast < current_ema_slow and 
                       current_price < current_ema_slow)
        
        except Exception:
            return False
    
    def reset(self) -> None:
        """Reset internal cooldown state."""

        self.filter.clear()

    def stats(self) -> dict:
        """Return diagnostic statistics for monitoring."""

        return self.filter.stats()
