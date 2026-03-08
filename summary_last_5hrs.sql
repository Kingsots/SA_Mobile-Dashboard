SELECT 
  COUNT(*) as total_count,
  signal,
  interval,
  triggered_by
FROM ml_signals 
WHERE timestamp >= '2026-02-19 04:00:00'
GROUP BY signal, interval, triggered_by
ORDER BY triggered_by, interval, signal;
