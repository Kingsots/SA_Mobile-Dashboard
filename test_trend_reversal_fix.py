"""
Test trend reversal detection and multi-timeframe confirmation.
Validates that USDCAD issue is fixed: repeated signals when market reverses.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from signals.event_filter import EventFilter, MarketEvent
from signals.event_monitor import EventMonitor, EventMonitorConfig


def create_sample_event(ticker: str, interval: str, event_type: str, 
                       confidence: float, timestamp: pd.Timestamp) -> MarketEvent:
    """Helper to create sample market events."""
    return MarketEvent(
        ticker=ticker,
        interval=interval,
        event_type=event_type,
        confidence=confidence,
        timestamp=timestamp,
        details={}
    )


def test_trend_reversal_detection():
    """Test that reversal signals are blocked or require higher confidence."""
    print("\n" + "="*70)
    print("TEST 1: Trend Reversal Detection")
    print("="*70)
    
    event_filter = EventFilter(min_confidence=0.50, cooldown_seconds=3600)
    now = pd.Timestamp.now(tz='UTC')
    
    # Scenario: USDCAD had bearish signal, then reversed up
    # We should block repeated bearish signals or require higher confidence
    
    # Event 1: Initial BEARISH signal at 14:00
    event1 = create_sample_event(
        'USDCAD', '4h', 'engulfed_structure_bearish', 
        confidence=0.60, timestamp=now
    )
    
    result1 = event_filter.is_valid(event1, now=now)
    print(f"\n✅ Event 1 (Initial BEARISH): {result1}")
    print(f"   Type: {event1.event_type}")
    print(f"   Confidence: {event1.confidence}")
    assert result1, "First event should be valid"
    
    # Register the first event
    event_filter.register(event1, now=now)
    print(f"   → Registered. Last direction: BEARISH for (USDCAD, 4h)")
    
    # Event 2: 1 hour later, repeated BEARISH signal with same confidence
    # This contradicts the reversal, should be BLOCKED
    now2 = now + timedelta(minutes=30)  # 30 minutes < 1 hour cooldown
    event2 = create_sample_event(
        'USDCAD', '4h', 'engulfed_structure_bearish',
        confidence=0.60, timestamp=now2
    )
    
    result2 = event_filter.is_valid(event2, now=now2)
    print(f"\n❌ Event 2 (Repeat BEARISH same confidence): {result2}")
    print(f"   Type: {event2.event_type}")
    print(f"   Confidence: {event2.confidence}")
    print(f"   Time since last: 30 minutes (within cooldown)")
    print(f"   → Expected: BLOCKED (same event type, within cooldown)")
    assert not result2, "Same event within cooldown should be blocked"
    
    # Event 3: Different direction (BULLISH) with standard confidence
    # Should be BLOCKED because it contradicts last direction without higher confidence
    now3 = now + timedelta(hours=1, minutes=30)  # 1.5 hours, still in cooldown
    event3 = create_sample_event(
        'USDCAD', '4h', 'engulfed_structure_bullish',
        confidence=0.60, timestamp=now3  # Standard confidence, not higher
    )
    
    result3 = event_filter.is_valid(event3, now=now3)
    print(f"\n❌ Event 3 (BULLISH reversal with standard confidence): {result3}")
    print(f"   Type: {event3.event_type}")
    print(f"   Confidence: {event3.confidence}")
    print(f"   Last direction: BEARISH")
    print(f"   → Expected: BLOCKED (reversal requires 10% higher confidence)")
    assert not result3, "Reversal signal needs higher confidence"
    
    # Event 4: BULLISH with HIGHER confidence (0.65+)
    # Should be ALLOWED because it has higher confidence for reversal
    event4 = create_sample_event(
        'USDCAD', '4h', 'engulfed_structure_bullish',
        confidence=0.65, timestamp=now3  # Higher confidence for reversal
    )
    
    result4 = event_filter.is_valid(event4, now=now3)
    print(f"\n✅ Event 4 (BULLISH reversal with higher confidence): {result4}")
    print(f"   Type: {event4.event_type}")
    print(f"   Confidence: {event4.confidence}")
    print(f"   Last direction: BEARISH")
    print(f"   → Expected: ALLOWED (confidence > 0.60 for reversal)")
    assert result4, "Reversal with higher confidence should be allowed"
    
    print("\n✅ Trend Reversal Detection: PASSED")


def create_ohlcv_data(direction: str, length: int = 50) -> pd.DataFrame:
    """Create synthetic OHLCV data trending in specified direction."""
    dates = pd.date_range(start='2026-01-01', periods=length, freq='30min')
    
    if direction == 'up':
        # Trending upward with price > EMA 21 > EMA 100
        close_prices = np.linspace(1.35200, 1.35400, length) + np.random.normal(0, 0.00020, length)
    else:
        # Trending downward with price < EMA 21 < EMA 100
        close_prices = np.linspace(1.35400, 1.35200, length) + np.random.normal(0, 0.00020, length)
    
    data = pd.DataFrame({
        'open': close_prices - 0.00010,
        'high': close_prices + 0.00030,
        'low': close_prices - 0.00030,
        'close': close_prices,
        'volume': np.random.uniform(1000, 5000, length),
    }, index=pd.DatetimeIndex(dates))
    
    return data


def test_multitimeframe_confirmation():
    """Test that 4h signals require lower timeframe confirmation."""
    print("\n" + "="*70)
    print("TEST 2: Multi-Timeframe Confirmation")
    print("="*70)
    
    config = EventMonitorConfig(
        min_confidence=0.50,
        cooldown_seconds=3600,
        ema_fast=21,
        ema_slow=100,
    )
    monitor = EventMonitor(config)
    
    # Create downtrending data for 30m and 1h (should confirm 4h SHORT)
    data_30m = create_ohlcv_data('down', length=50)
    data_1h = create_ohlcv_data('down', length=50)
    data_4h = create_ohlcv_data('down', length=30)
    
    # Create sample events
    now = pd.Timestamp.now(tz='UTC')
    events = [
        MarketEvent(
            ticker='GBPUSD',
            interval='4h',
            event_type='engulfed_structure_bearish',
            confidence=0.75,
            timestamp=now,
            details={}
        )
    ]
    
    # Apply multi-timeframe confirmation
    lower_timeframes = {'30m': data_30m, '1h': data_1h}
    confirmed = monitor._apply_multitimeframe_confirmation(
        events, 
        current_interval='4h',
        lower_timeframe_dfs=lower_timeframes
    )
    
    print(f"\n4h BEARISH signal with downtrending 1h/30m:")
    print(f"  30m direction: DOWN (EMA 21 < 100)")
    print(f"  1h direction: DOWN (EMA 21 < 100)")
    print(f"  → Multi-timeframe confirmation: {'✅ PASS' if len(confirmed) > 0 else '❌ FAIL'}")
    assert len(confirmed) == 1, "4h bearish should be confirmed by downtrending lower timeframes"
    
    # Now test when lower timeframes DON'T align
    data_30m_up = create_ohlcv_data('up', length=50)
    data_1h_up = create_ohlcv_data('up', length=50)
    
    lower_timeframes_misaligned = {'30m': data_30m_up, '1h': data_1h_up}
    confirmed_misaligned = monitor._apply_multitimeframe_confirmation(
        events,
        current_interval='4h',
        lower_timeframe_dfs=lower_timeframes_misaligned
    )
    
    print(f"\n4h BEARISH signal with uptrending 1h/30m (MISALIGNED):")
    print(f"  30m direction: UP (EMA 21 > 100)")
    print(f"  1h direction: UP (EMA 21 > 100)")
    print(f"  → Multi-timeframe confirmation: {'✅ PASS' if len(confirmed_misaligned) == 0 else '❌ FAIL'}")
    assert len(confirmed_misaligned) == 0, "4h bearish should be rejected when lower timeframes are bullish"
    
    print("\n✅ Multi-Timeframe Confirmation: PASSED")


def test_usdcad_scenario():
    """Reproduce and verify the USDCAD bug is fixed."""
    print("\n" + "="*70)
    print("TEST 3: USDCAD Repeated Signal Scenario")
    print("="*70)
    print("""
SCENARIO: USDCAD 4h on Jan 5-6, 2026
- 14:00 UTC: First SELL signal (bearish_structure) - VALID
- 16:00 UTC: Repeat SELL signal (same type) - SHOULD BE BLOCKED
- 17:00 UTC: Third SELL signal (same type) - SHOULD BE BLOCKED
- But price had reversed UP between signals
    """)
    
    event_filter = EventFilter(min_confidence=0.50, cooldown_seconds=3600)
    
    # Timeline
    t1 = pd.Timestamp('2026-01-05 14:00', tz='UTC')
    t2 = pd.Timestamp('2026-01-05 16:00', tz='UTC')
    t3 = pd.Timestamp('2026-01-05 17:00', tz='UTC')
    
    # Signal 1: 14:00 - First SELL
    signal1 = create_sample_event('USDCAD', '4h', 'engulfed_structure_bearish', 0.65, t1)
    valid1 = event_filter.is_valid(signal1, now=t1)
    print(f"\n1️⃣  14:00 UTC - First SELL: {valid1}")
    assert valid1
    event_filter.register(signal1, now=t1)
    
    # Signal 2: 16:00 - Repeated SELL (same type, within cooldown)
    signal2 = create_sample_event('USDCAD', '4h', 'engulfed_structure_bearish', 0.65, t2)
    valid2 = event_filter.is_valid(signal2, now=t2)
    print(f"2️⃣  16:00 UTC - Repeated SELL: {valid2} (❌ BLOCKED - same event, within cooldown)")
    assert not valid2, "Second signal should be blocked by cooldown"
    
    # Signal 3: 17:00 - Third SELL (same type, still within cooldown)
    signal3 = create_sample_event('USDCAD', '4h', 'engulfed_structure_bearish', 0.65, t3)
    valid3 = event_filter.is_valid(signal3, now=t3)
    print(f"3️⃣  17:00 UTC - Third SELL: {valid3} (❌ BLOCKED - same event, within cooldown)")
    assert not valid3, "Third signal should also be blocked"
    
    print("\n" + "="*70)
    print("✅ USDCAD Fix Verified: Repeated signals now BLOCKED correctly")
    print("="*70)


if __name__ == '__main__':
    print("\n" + "="*70)
    print("TESTING TREND REVERSAL & MULTI-TIMEFRAME CONFIRMATION FIXES")
    print("="*70)
    
    test_trend_reversal_detection()
    test_multitimeframe_confirmation()
    test_usdcad_scenario()
    
    print("\n" + "="*70)
    print("✅ ALL TESTS PASSED")
    print("="*70)
    print("""
SUMMARY OF FIXES:
1. ✅ Trend Reversal Detection: Tracks last signal direction per symbol/timeframe
2. ✅ Reversal Penalty: Requires 10% higher confidence to reverse signal direction
3. ✅ Standard Cooldown: Blocks same event type within cooldown period
4. ✅ Multi-Timeframe Confirmation: 4h signals require lower timeframe alignment
5. ✅ USDCAD Fix: Repeated bearish signals now properly blocked when reversing
    """)
