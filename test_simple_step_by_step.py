"""
STEP 1: Simple isolated test of EventFilter reversal detection logic.
NO complex event creation - just testing the core logic.
"""

import pandas as pd
from datetime import timedelta
from signals.event_filter import EventFilter, MarketEvent


def test_step1_basic_cooldown():
    """Test that basic cooldown works (no reversal logic yet)."""
    print("\n" + "="*70)
    print("STEP 1: Basic Cooldown (No Reversal Logic)")
    print("="*70)
    
    ef = EventFilter(min_confidence=0.50, cooldown_seconds=3600)
    now = pd.Timestamp('2026-01-05 14:00', tz='UTC')
    
    # Create a simple event
    event = MarketEvent(
        ticker='USDCAD',
        interval='4h',
        event_type='engulfed_structure_bearish',
        confidence=0.65,
        timestamp=now,
        details={}
    )
    
    # Event should pass (first time)
    valid1 = ef.is_valid(event, now=now)
    print(f"\n✅ Event 1 (first time): {valid1}")
    assert valid1 == True, "First event should be valid"
    
    # Register it
    ef.register(event, now=now)
    print(f"   → Registered event")
    
    # Try same event 30 min later (within 1h cooldown)
    now2 = now + timedelta(minutes=30)
    event2 = MarketEvent(
        ticker='USDCAD',
        interval='4h',
        event_type='engulfed_structure_bearish',  # SAME TYPE
        confidence=0.65,
        timestamp=now2,
        details={}
    )
    
    valid2 = ef.is_valid(event2, now=now2)
    print(f"\n❌ Event 2 (30min later, same type): {valid2}")
    print(f"   Expected: False (same event type, within cooldown)")
    assert valid2 == False, "Same event within cooldown should be rejected"
    
    # Try different event (different type) 30 min later - should PASS
    event3 = MarketEvent(
        ticker='USDCAD',
        interval='4h',
        event_type='higher_high_breakout',  # DIFFERENT TYPE
        confidence=0.65,
        timestamp=now2,
        details={}
    )
    
    valid3 = ef.is_valid(event3, now=now2)
    print(f"\n✅ Event 3 (30min later, DIFFERENT type): {valid3}")
    print(f"   Expected: True (different event type, no conflict)")
    assert valid3 == True, "Different event type should pass"
    
    print("\n" + "="*70)
    print("✅ STEP 1 PASSED: Basic cooldown works correctly")
    print("="*70)


def test_step2_direction_tracking():
    """Test that last direction is tracked and retrieved."""
    print("\n" + "="*70)
    print("STEP 2: Direction Tracking (Core of Reversal Logic)")
    print("="*70)
    
    ef = EventFilter(min_confidence=0.50, cooldown_seconds=3600)
    now = pd.Timestamp('2026-01-05 14:00', tz='UTC')
    
    # Event 1: BEARISH
    event_bearish = MarketEvent(
        ticker='GBPUSD',
        interval='4h',
        event_type='engulfed_structure_bearish',
        confidence=0.65,
        timestamp=now,
        details={}
    )
    
    # Extract direction
    direction = ef._get_signal_direction(event_bearish)
    print(f"\n1. BEARISH event direction extracted: {direction}")
    assert direction == 'SHORT', "Bearish should map to SHORT"
    
    # Validate and register
    valid = ef.is_valid(event_bearish, now=now)
    assert valid == True
    ef.register(event_bearish, now=now)
    print(f"   → Registered. Last direction for (GBPUSD, 4h): {direction}")
    
    # Check internal state
    key = ('GBPUSD', '4h')
    assert key in ef._last_direction, "Direction should be tracked"
    assert ef._last_direction[key] == 'SHORT', "Direction should be SHORT"
    print(f"   ✅ Internal state correct: {ef._last_direction[key]}")
    
    # Event 2: BULLISH (opposite direction) - same time with LOW confidence
    now2 = now + timedelta(minutes=30)
    event_bullish = MarketEvent(
        ticker='GBPUSD',
        interval='4h',
        event_type='engulfed_structure_bullish',
        confidence=0.55,  # Below 0.60 threshold
        timestamp=now2,
        details={}
    )
    
    direction2 = ef._get_signal_direction(event_bullish)
    print(f"\n2. BULLISH event direction extracted: {direction2}")
    assert direction2 == 'LONG', "Bullish should map to LONG"
    
    # This should be REJECTED because:
    # - Different direction (LONG vs SHORT)
    # - Within cooldown period
    # - Confidence not high enough (0.55 < 0.60 required for reversal)
    valid2 = ef.is_valid(event_bullish, now=now2)
    print(f"   Validation result: {valid2}")
    print(f"   Expected: False (reversal attempt with confidence 0.55 < threshold 0.60)")
    assert valid2 == False, "Reversal should require higher confidence"
    
    # Event 3: BULLISH with HIGHER confidence
    event_bullish_high = MarketEvent(
        ticker='GBPUSD',
        interval='4h',
        event_type='engulfed_structure_bullish',
        confidence=0.65,  # Note: min_confidence=0.50, so reversal threshold = 0.60, and 0.65 > 0.60
        timestamp=now2,
        details={}
    )
    
    valid3 = ef.is_valid(event_bullish_high, now=now2)
    print(f"\n3. BULLISH with confidence 0.65 (threshold is 0.60 for reversal): {valid3}")
    print(f"   Expected: True (meets reversal threshold)")
    assert valid3 == True, "Reversal with sufficient confidence should pass"
    
    print("\n" + "="*70)
    print("✅ STEP 2 PASSED: Direction tracking works correctly")
    print("="*70)


def test_step3_reversal_threshold():
    """Test the reversal threshold calculation."""
    print("\n" + "="*70)
    print("STEP 3: Reversal Threshold Calculation")
    print("="*70)
    
    ef = EventFilter(min_confidence=0.50, cooldown_seconds=3600)
    now = pd.Timestamp('2026-01-05 14:00', tz='UTC')
    
    print(f"\nConfiguration:")
    print(f"  min_confidence: {ef.min_confidence}")
    print(f"  reversal_threshold: {ef.min_confidence + 0.10} (min_confidence + 0.10)")
    
    # Register BEARISH signal
    event1 = MarketEvent(
        ticker='EURUSD',
        interval='4h',
        event_type='engulfed_structure_bearish',
        confidence=0.55,
        timestamp=now,
        details={}
    )
    
    valid1 = ef.is_valid(event1, now=now)
    assert valid1 == True
    ef.register(event1, now=now)
    print(f"\n1. Registered BEARISH with confidence 0.55")
    
    # Try BULLISH at different confidence levels
    now2 = now + timedelta(minutes=30)
    
    for confidence in [0.55, 0.59, 0.60, 0.61]:
        event = MarketEvent(
            ticker='EURUSD',
            interval='4h',
            event_type='engulfed_structure_bullish',
            confidence=confidence,
            timestamp=now2,
            details={}
        )
        
        valid = ef.is_valid(event, now=now2)
        status = "✅ PASS" if valid else "❌ BLOCK"
        print(f"\n2. BULLISH reversal with confidence {confidence}: {status}")
        
        if confidence < 0.60:
            assert valid == False, f"Confidence {confidence} should be rejected (< 0.60)"
        else:
            assert valid == True, f"Confidence {confidence} should be accepted (>= 0.60)"
    
    print("\n" + "="*70)
    print("✅ STEP 3 PASSED: Reversal threshold works correctly")
    print("="*70)


if __name__ == '__main__':
    print("\n" + "="*70)
    print("SYSTEMATIC VERIFICATION - STEP BY STEP")
    print("="*70)
    
    try:
        test_step1_basic_cooldown()
        test_step2_direction_tracking()
        test_step3_reversal_threshold()
        
        print("\n" + "="*70)
        print("✅ ALL STEPS PASSED - CODE IS NOT BROKEN")
        print("="*70)
        print("""
VERIFIED:
1. ✅ Basic cooldown logic works (same event blocked within window)
2. ✅ Direction tracking works (BEARISH→SHORT, BULLISH→LONG)
3. ✅ Reversal threshold works (opposite direction needs +10% confidence)
        """)
    
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
