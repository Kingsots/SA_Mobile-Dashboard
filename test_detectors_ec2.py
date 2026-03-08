#!/usr/bin/env python3
"""Test each detector function with current EC2 data."""
import sys
sys.path.insert(0, '/home/ubuntu/opticore-bot')

import sqlite3
import pandas as pd
from signals.market_structure import detect_higher_high_breakout, detect_lower_low_breakdown, detect_structure_shift
from signals.volume_volatility import detect_volume_spike, detect_atr_expansion
from signals.momentum_confirmation import detect_rsi_shift, detect_ema_crossover

conn = sqlite3.connect('/home/ubuntu/opticore-bot/trading_bot.db')
df = pd.read_sql_query("SELECT * FROM ohlcv_data WHERE symbol='XAUUSD' AND interval='1h' ORDER BY timestamp DESC LIMIT 50", conn)
df = df.iloc[::-1].reset_index(drop=True)
conn.close()

print(f"Loaded {len(df)} candles for XAUUSD 1h")
print(f"Latest: {df.iloc[-1]['timestamp']}")
print("=" * 60)

results = {
    'Higher High Breakout': detect_higher_high_breakout(df, lookback=20, min_break_ratio=0.0005),
    'Lower Low Breakdown': detect_lower_low_breakdown(df, lookback=20, min_break_ratio=0.0005),
    'Structure Shift': detect_structure_shift(df),
    'Volume Spike': detect_volume_spike(df, lookback=20),
    'ATR Expansion': detect_atr_expansion(df, lookback=20),
    'RSI Shift': detect_rsi_shift(df, lookback=20),
    'EMA Crossover': detect_ema_crossover(df),
}

for name, result in results.items():
    print(f"{name}: {result}")
