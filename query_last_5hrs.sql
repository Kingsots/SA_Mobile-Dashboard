SELECT 
  timestamp, 
  ticker, 
  interval, 
  signal, 
  ROUND(confidence, 4) as confidence,
  triggered_by
FROM ml_signals 
WHERE timestamp >= '2026-02-19 04:00:00'
ORDER BY timestamp DESC, ticker, interval;
