.mode column
.headers on
SELECT 
  COUNT(*) as total_candles,
  COUNT(DISTINCT ticker) as unique_symbols,
  COUNT(DISTINCT timeframe) as unique_intervals,
  MIN(timestamp) as first_candle,
  MAX(timestamp) as last_candle
FROM ohlcv_data 
WHERE timestamp > datetime('now', '-5 hours');

SELECT '=== BREAKDOWN BY SYMBOL AND INTERVAL ===' as label;

SELECT 
  ticker,
  timeframe,
  COUNT(*) as candles,
  MIN(timestamp) as first,
  MAX(timestamp) as last
FROM ohlcv_data
WHERE timestamp > datetime('now', '-5 hours')
GROUP BY ticker, timeframe
ORDER BY ticker, timeframe;
