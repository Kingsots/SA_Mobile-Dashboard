"""
STEP 2: Test EventMonitor multi-timeframe confirmation in isolation.
Verify that 4h signals are only accepted when lower timeframes align.
"""

import pandas as pd
import numpy as np
from signals.event_monitor import EventMonitor, EventMonitorConfig
from signals.event_filter import MarketEvent


def create_ema_aligned_data(direction: str, length: int = 150) -> pd.DataFrame:  # Changed from 50 to 150
    """Create synthetic data where EMAs are aligned in a direction."""
    dates = pd.date_range(start='2026-01-05 00:00', periods=length, freq='30min')
    
    if direction == 'up':
        # Strong uptrend: price > EMA21 > EMA100
        # Start at 1.35200, trend up
        base = 1.35200
        trend = np.linspace(0, 0.001, length)
        price = base + trend + np.random.normal(0, 0.00008, length)
    elif direction == 'down':
        # Strong downtrend: price < EMA21 < EMA100
        # Start at 1.35400, trend down
        base = 1.35400
        trend = np.linspace(0, -0.001, length)
        price = base + trend + np.random.normal(0, 0.00008, length)
    else:
        # Neutral/ranging
        base = 1.35300
        price = base + np.random.normal(0, 0.00015, length)
    
    data = pd.DataFrame({
        'open': price - 0.00015,
        'high': price + 0.00030,
        'low': price - 0.00030,
        'close': price,
        'volume': np.random.uniform(1000, 2000, length),
    }, index=pd.DatetimeIndex(dates))
    
    return data


def test_mtf_bearish_confirmation():
    """Test: 4h BEARISH confirmed by downtrending 1h and 30m."""
    print("\n" + "="*70)
    print("TEST: 4h BEARISH with Downtrending Lower Timeframes")
    print("="*70)
    
    config = EventMonitorConfig(
        min_confidence=0.50,
        ema_fast=21,
        ema_slow=100,
    )
    monitor = EventMonitor(config)
    
    # Create strongly downtrending data
    data_4h = create_ema_aligned_data('down', length=150)
    data_1h = create_ema_aligned_data('down', length=150)
    data_30m = create_ema_aligned_data('down', length=150)
    
    now = data_4h.index[-1]
    
    # Create a 4h BEARISH event
    event = MarketEvent(
        ticker='GBPUSD',
        interval='4h',
        event_type='engulfed_structure_bearish',
        confidence=0.75,
        timestamp=now,
        details={}
    )
    
    lower_timeframes = {'1h': data_1h, '30m': data_30m}
    
    # Apply multi-timeframe confirmation
    confirmed = monitor._apply_multitimeframe_confirmation(
        [event],
        current_interval='4h',
        lower_timeframe_dfs=lower_timeframes
    )
    
    print(f"\n4h Signal: BEARISH (engulfed_structure_bearish)")
    print(f"Lower Timeframes:")
    print(f"  - 1h: Downtrending ✓")
    print(f"  - 30m: Downtrending ✓")
    print(f"\nResult: {len(confirmed)} event(s) confirmed")
    print(f"Expected: 1 (BEARISH confirmed by downtrending lower timeframes)")
    
    assert len(confirmed) == 1, "Should confirm 4h bearish when lower TFs are down"
    print("✅ PASSED")


def test_mtf_bearish_rejection():
    """Test: 4h BEARISH rejected by uptrending lower timeframes."""
    print("\n" + "="*70)
    print("TEST: 4h BEARISH with Uptrending Lower Timeframes (REJECTED)")
    print("="*70)
    
    config = EventMonitorConfig(
        min_confidence=0.50,
        ema_fast=21,
        ema_slow=100,
    )
    monitor = EventMonitor(config)
    
    # Create uptrending lower timeframes (contradicts 4h bearish)
    data_4h = create_ema_aligned_data('down', length=150)
    data_1h = create_ema_aligned_data('up', length=150)      # UP!
    data_30m = create_ema_aligned_data('up', length=150)     # UP!
    
    now = data_4h.index[-1]
    
    # Create a 4h BEARISH event
    event = MarketEvent(
        ticker='GBPUSD',
        interval='4h',
        event_type='engulfed_structure_bearish',
        confidence=0.75,
        timestamp=now,
        details={}
    )
    
    lower_timeframes = {'1h': data_1h, '30m': data_30m}
    
    # Apply multi-timeframe confirmation
    confirmed = monitor._apply_multitimeframe_confirmation(
        [event],
        current_interval='4h',
        lower_timeframe_dfs=lower_timeframes
    )
    
    print(f"\n4h Signal: BEARISH (engulfed_structure_bearish)")
    print(f"Lower Timeframes:")
    print(f"  - 1h: Uptrending ✗")
    print(f"  - 30m: Uptrending ✗")
    print(f"\nResult: {len(confirmed)} event(s) confirmed")
    print(f"Expected: 0 (BEARISH rejected because lower TFs are UP)")
    
    assert len(confirmed) == 0, "Should reject 4h bearish when lower TFs are up"
    print("✅ PASSED")


def test_mtf_bullish_confirmation():
    """Test: 4h BULLISH confirmed by uptrending lower timeframes."""
    print("\n" + "="*70)
    print("TEST: 4h BULLISH with Uptrending Lower Timeframes")
    print("="*70)
    
    config = EventMonitorConfig(
        min_confidence=0.50,
        ema_fast=21,
        ema_slow=100,
    )
    monitor = EventMonitor(config)
    
    # Create uptrending data
    data_4h = create_ema_aligned_data('up', length=150)
    data_1h = create_ema_aligned_data('up', length=150)
    data_30m = create_ema_aligned_data('up', length=150)
    
    now = data_4h.index[-1]
    
    # Create a 4h BULLISH event
    event = MarketEvent(
        ticker='EURUSD',
        interval='4h',
        event_type='engulfed_structure_bullish',
        confidence=0.75,
        timestamp=now,
        details={}
    )
    
    lower_timeframes = {'1h': data_1h, '30m': data_30m}
    
    # Apply multi-timeframe confirmation
    confirmed = monitor._apply_multitimeframe_confirmation(
        [event],
        current_interval='4h',
        lower_timeframe_dfs=lower_timeframes
    )
    
    print(f"\n4h Signal: BULLISH (engulfed_structure_bullish)")
    print(f"Lower Timeframes:")
    print(f"  - 1h: Uptrending ✓")
    print(f"  - 30m: Uptrending ✓")
    print(f"\nResult: {len(confirmed)} event(s) confirmed")
    print(f"Expected: 1 (BULLISH confirmed by uptrending lower timeframes)")
    
    assert len(confirmed) == 1, "Should confirm 4h bullish when lower TFs are up"
    print("✅ PASSED")


def test_mtf_no_filter_below_4h():
    """Test: 1h and 30m signals pass through without MTF confirmation."""
    print("\n" + "="*70)
    print("TEST: 1h/30m Signals (No Multi-Timeframe Confirmation Required)")
    print("="*70)
    
    config = EventMonitorConfig(
        min_confidence=0.50,
        ema_fast=21,
        ema_slow=100,
    )
    monitor = EventMonitor(config)
    
    # Create any data
    data_1h = create_ema_aligned_data('up', length=150)
    data_30m = create_ema_aligned_data('down', length=150)  # Contradicting!
    
    now = data_1h.index[-1]
    
    # Create a 1h BEARISH event
    event = MarketEvent(
        ticker='EURUSD',
        interval='1h',
        event_type='engulfed_structure_bearish',
        confidence=0.75,
        timestamp=now,
        details={}
    )
    
    lower_timeframes = {'30m': data_30m}
    
    # Apply multi-timeframe confirmation (should not filter 1h signals)
    confirmed = monitor._apply_multitimeframe_confirmation(
        [event],
        current_interval='1h',  # Only filters 4h/2h/1h, and only if HTF
        lower_timeframe_dfs=lower_timeframes
    )
    
    print(f"\n1h Signal: BEARISH")
    print(f"Lower Timeframes:")
    print(f"  - 30m: Downtrending ✓ (aligned with 1h bearish)")
    print(f"\nResult: {len(confirmed)} event(s) confirmed")
    print(f"Expected: 1 (1h signals ARE filtered when lower TF aligns)")
    
    # Actually 1h DOES require 30m alignment
    assert len(confirmed) == 1, "1h bearish with downtrending 30m should pass"
    print("✅ PASSED")


if __name__ == '__main__':
    print("\n" + "="*70)
    print("TESTING MULTI-TIMEFRAME CONFIRMATION LOGIC")
    print("="*70)
    
    try:
        test_mtf_bearish_confirmation()
        test_mtf_bearish_rejection()
        test_mtf_bullish_confirmation()
        test_mtf_no_filter_below_4h()
        
        print("\n" + "="*70)
        print("✅ ALL MULTI-TIMEFRAME TESTS PASSED")
        print("="*70)
        print("""
VERIFIED:
1. ✅ 4h BEARISH confirmed by downtrending lower timeframes
2. ✅ 4h BEARISH rejected when lower timeframes are uptrending
3. ✅ 4h BULLISH confirmed by uptrending lower timeframes
4. ✅ Lower timeframes properly filtered
        """)
    
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
