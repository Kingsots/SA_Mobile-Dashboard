"""
Debug: Check what's happening in _check_timeframe_alignment
"""

import pandas as pd
import numpy as np
from signals.event_monitor import EventMonitor, EventMonitorConfig


def create_downtrend_data(length: int = 150) -> pd.DataFrame:  # Changed to 150!
    """Create synthetic downtrending data."""
    dates = pd.date_range(start='2026-01-05 00:00', periods=length, freq='30min')
    base = 1.35400
    trend = np.linspace(0, -0.001, length)
    price = base + trend + np.random.normal(0, 0.00008, length)
    
    data = pd.DataFrame({
        'open': price - 0.00015,
        'high': price + 0.00030,
        'low': price - 0.00030,
        'close': price,
        'volume': np.random.uniform(1000, 2000, length),
    }, index=pd.DatetimeIndex(dates))
    
    return data


# Create test data
data_30m = create_downtrend_data(150)  # Need at least 105 rows (100 + 5)

config = EventMonitorConfig(
    min_confidence=0.50,
    ema_fast=21,
    ema_slow=100,
)
monitor = EventMonitor(config)

# Check alignment
print("Testing _check_timeframe_alignment")
print("="*70)
print(f"\nData length: {len(data_30m)}")
print(f"Last 5 closes:\n{data_30m['close'].tail()}")

# Calculate EMAs manually to debug
ema_fast = data_30m['close'].ewm(span=21, adjust=False).mean()
ema_slow = data_30m['close'].ewm(span=100, adjust=False).mean()

print(f"\nLast EMA 21: {ema_fast.iloc[-1]:.8f}")
print(f"Last EMA 100: {ema_slow.iloc[-1]:.8f}")
print(f"Last close: {data_30m['close'].iloc[-1]:.8f}")

print(f"\nAlignment checks for SHORT (downtrend):")
print(f"  EMA21 < EMA100: {ema_fast.iloc[-1] < ema_slow.iloc[-1]}")
print(f"  Price < EMA100: {data_30m['close'].iloc[-1] < ema_slow.iloc[-1]}")

# Call the method
result = monitor._check_timeframe_alignment(data_30m, 'SHORT')
print(f"\nResult: {result}")
print(f"Expected: True (downtrending data should align with SHORT)")
