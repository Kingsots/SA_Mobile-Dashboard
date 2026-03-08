SELECT 
  COUNT(*) as total_candles,
  COUNT(DISTINCT ticker) as symbols,
  COUNT(DISTINCT interval) as intervals,
  MIN(timestamp) as earliest,
  MAX(timestamp) as latest
FROM ohlcv
WHERE timestamp >= datetime('now', '-5 hours');

SELECT '=== BREAKDOWN BY SYMBOL AND INTERVAL ===' as "";

SELECT 
  ticker,
  interval,
  COUNT(*) as candles,
  MIN(timestamp) as first_candle,
  MAX(timestamp) as last_candle
FROM ohlcv
WHERE timestamp >= datetime('now', '-5 hours')
GROUP BY ticker, interval
ORDER BY ticker, interval;
