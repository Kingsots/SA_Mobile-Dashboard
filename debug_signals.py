#!/usr/bin/env python3
"""Debug script to investigate signal generation issues"""

from core.database import DatabaseManager
from core.config import Config
from datetime import datetime, timedelta

db = DatabaseManager()

print("=" * 70)
print("  DEBUG: Signal Generation Investigation")
print("=" * 70)

# 1. Check OHLCV data availability
print("\n1️⃣  OHLCV Data Status:")
for symbol in Config.get_symbol_list()[:3]:
    df = db.load_ohlcv_data(symbol, '1h', limit=10)
    if df is None or df.empty:
        print(f"   {symbol}: ❌ No data")
    else:
        last_time = df.index[-1] if hasattr(df.index[-1], 'strftime') else df.index[-1]
        print(f"   {symbol}: ✅ {len(df)} rows, last: {last_time}")

# 2. Check ml_signals table stats
print("\n2️⃣  ml_signals Table Status:")

try:
    stats = db.get_database_stats()
    total_signals = stats.get('total_signals', 0)
    print(f"   Total signals: {total_signals}")
except Exception as e:
    print(f"   Error querying signals: {e}")
    total_signals = 0

# 3. Check model availability
print("\n3️⃣  Model Status:")
model_exists = Config.MODEL_CURRENT_PATH.exists()
print(f"   Model file: {'✅ exists' if model_exists else '❌ missing'}")

# 4. Check configuration
print("\n4️⃣  Signal Generation Config:")
print(f"   EVENT_MODE_ENABLED: {Config.EVENT_MODE_ENABLED}")
print(f"   ENABLE_TIME_TRIGGERED_SIGNALS: {Config.ENABLE_TIME_TRIGGERED_SIGNALS}")
print(f"   USE_TIINGO_PIPELINE: {Config.USE_TIINGO_PIPELINE}")

# 5. Check watchlist
print("\n5️⃣  Watchlist:")
symbols = Config.get_symbol_list()
print(f"   Count: {len(symbols)}")
print(f"   Symbols: {symbols}")

# 6. Check event monitor
print("\n6️⃣  Event Monitor:")
from signals.event_monitor import EventMonitor
em = EventMonitor()
print(f"   EventMonitor initialized: ✅")

# Test event detection on one symbol
symbol = "EURUSD"
df = db.load_ohlcv_data(symbol, '1h', limit=50)
if df is not None and not df.empty:
    events = em.analyze(symbol, '1h', df)
    print(f"   Events detected on {symbol}: {len(events) if events else 0}")
    if events:
        for i, event in enumerate(events[:3]):
            print(f"      • Event {i+1}: {event}")
else:
    print(f"   ❌ No data for {symbol} to test event detection")

print("\n" + "=" * 70)
