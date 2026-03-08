import sqlite3

db = "/home/ubuntu/SilentAnalyst/trading_bot.db"
conn = sqlite3.connect(db)
cursor = conn.cursor()

print("=" * 80)
print("FRESH TIINGO DATA - LAST 5 HOURS")
print("=" * 80)

# Aggregate stats
cursor.execute("""
SELECT 
  COUNT(*) as total_candles,
  COUNT(DISTINCT symbol) as unique_symbols,
  COUNT(DISTINCT timeframe) as unique_timeframes,
  MIN(timestamp) as earliest,
  MAX(timestamp) as latest
FROM ohlcv_data 
WHERE timestamp > datetime('now', '-5 hours')
""")

row = cursor.fetchone()
if row:
    total, symbols, frames, earliest, latest = row
    print(f"\nTotal fresh candles ingested: {total}")
    print(f"Unique symbols: {symbols}")
    print(f"Unique timeframes: {frames}")
    print(f"Time range: {earliest} to {latest}")

# Breakdown
print("\n" + "=" * 80)
print("BREAKDOWN BY SYMBOL AND TIMEFRAME")
print("=" * 80)
cursor.execute("""
SELECT 
  symbol,
  timeframe,
  COUNT(*) as candles,
  MIN(timestamp) as first_candle,
  MAX(timestamp) as most_recent
FROM ohlcv_data
WHERE timestamp > datetime('now', '-5 hours')
GROUP BY symbol, timeframe
ORDER BY symbol, timeframe
""")

print(f"\n{'SYMBOL':<10} {'FRAME':<8} {'CANDLES':<8} {'FIRST':<25} {'MOST RECENT':<25}")
print("-" * 80)

for row in cursor.fetchall():
    symbol, frame, count, first, last = row
    print(f"{symbol:<10} {frame:<8} {count:<8} {first:<25} {last:<25}")

conn.close()
