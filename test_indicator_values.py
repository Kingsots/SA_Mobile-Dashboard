#!/usr/bin/env python
"""Test indicator values to understand why events aren't firing."""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path

# Connect to DB
db_path = Path('trading_bot.db')
conn = sqlite3.connect(db_path)

# Load EURUSD data
query = '''
SELECT timestamp, open, high, low, close, volume 
FROM ohlcv_data 
WHERE symbol = 'EURUSD' AND timeframe = '1h'
ORDER BY timestamp ASC
'''
df = pd.read_sql_query(query, conn)
conn.close()

if df.empty:
    print("No data found!")
    exit(1)

df['timestamp'] = pd.to_datetime(df['timestamp'])
df.set_index('timestamp', inplace=True)
print(f"Loaded {len(df)} EURUSD 1h candles")
print(f"Date range: {df.index[0]} to {df.index[-1]}\n")

# Get last 250 for analysis
df_recent = df.tail(250).copy()

# Calculate EMAs
df_recent['EMA21'] = df_recent['close'].ewm(span=21, adjust=False).mean()
df_recent['EMA100'] = df_recent['close'].ewm(span=100, adjust=False).mean()

# Calculate RSI
def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(to_replace=0, value=np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi

df_recent['RSI'] = calc_rsi(df_recent['close'], 14)

# Calculate ATR
df_recent['TR'] = np.maximum(
    df_recent['high'] - df_recent['low'],
    np.maximum(
        abs(df_recent['high'] - df_recent['close'].shift()),
        abs(df_recent['low'] - df_recent['close'].shift())
    )
)
df_recent['ATR'] = df_recent['TR'].rolling(window=14).mean()

# Calculate volume metrics
df_recent['SMA_VOL'] = df_recent['volume'].rolling(window=20).mean()
df_recent['VOL_RATIO'] = df_recent['volume'] / (df_recent['SMA_VOL'] + 1e-9)

print("=" * 80)
print("INDICATOR ANALYSIS - Last 20 Candles")
print("=" * 80)

last_20 = df_recent.tail(20).copy()
for idx, (ts, row) in enumerate(last_20.iterrows(), 1):
    print(f"\n{idx:2d}. {ts.strftime('%Y-%m-%d %H:%M')}")
    print(f"    Close: {row['close']:.6f}")
    print(f"    EMA21: {row['EMA21']:.6f}  EMA100: {row['EMA100']:.6f}  Separation: {abs(row['EMA21']-row['EMA100'])/row['EMA100']*100:.4f}%")
    print(f"    RSI: {row['RSI']:.2f}")
    print(f"    ATR: {row['ATR']:.6f} ({row['ATR']/row['close']*100:.3f}%)")
    print(f"    Vol Ratio: {row['VOL_RATIO']:.2f}x")

# Check for crossovers in last 10
print("\n" + "=" * 80)
print("EMA CROSSOVER CHECK (Last 10 Candles)")
print("=" * 80)

last_10 = df_recent.tail(10).copy()
for i in range(1, len(last_10)):
    prev_fast = last_10['EMA21'].iloc[i-1]
    prev_slow = last_10['EMA100'].iloc[i-1]
    curr_fast = last_10['EMA21'].iloc[i]
    curr_slow = last_10['EMA100'].iloc[i]
    
    crossed_up = prev_fast < prev_slow and curr_fast > curr_slow
    crossed_down = prev_fast > prev_slow and curr_fast < curr_slow
    
    if crossed_up or crossed_down:
        direction = "BULLISH" if crossed_up else "BEARISH"
        separation = abs(curr_fast - curr_slow) / max(curr_slow, 1e-9)
        print(f"✅ EMA CROSSOVER {direction} at {last_10.index[i].strftime('%Y-%m-%d %H:%M')}")
        print(f"   Separation: {separation*100:.4f}% (threshold: 0.1%)")
    else:
        separation = abs(curr_fast - curr_slow) / max(curr_slow, 1e-9)
        print(f"   {last_10.index[i].strftime('%Y-%m-%d %H:%M')}: Separation {separation*100:.4f}%")

# Check structure
print("\n" + "=" * 80)
print("STRUCTURE ANALYSIS (Higher Highs / Lower Lows)")
print("=" * 80)

lookback = 15
last_lookback = df_recent.tail(lookback + 1).copy()

# Higher highs
reference_high = last_lookback['high'].iloc[:-1].max()
latest_high = last_lookback['high'].iloc[-1]
breakout_ratio = (latest_high - reference_high) / reference_high if reference_high != 0 else 0

print(f"\nHigher High Breakout (lookback={lookback}):")
print(f"  Reference high: {reference_high:.6f}")
print(f"  Latest high: {latest_high:.6f}")
print(f"  Breakout ratio: {breakout_ratio*100:.4f}% (threshold: 0.15%)")
if breakout_ratio > 0.0015:
    print(f"  ✅ WOULD TRIGGER BREAKOUT")
else:
    print(f"  ❌ Below threshold")

# Lower lows
reference_low = last_lookback['low'].iloc[:-1].min()
latest_low = last_lookback['low'].iloc[-1]
breakdown_ratio = (reference_low - latest_low) / reference_low if reference_low != 0 else 0

print(f"\nLower Low Breakdown (lookback={lookback}):")
print(f"  Reference low: {reference_low:.6f}")
print(f"  Latest low: {latest_low:.6f}")
print(f"  Breakdown ratio: {breakdown_ratio*100:.4f}% (threshold: 0.15%)")
if breakdown_ratio > 0.0015:
    print(f"  ✅ WOULD TRIGGER BREAKDOWN")
else:
    print(f"  ❌ Below threshold")

print("\n" + "=" * 80)
