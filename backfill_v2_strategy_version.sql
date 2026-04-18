-- Preview what will change (read-only check)
SELECT id, trade_id, ticker, strategy_version, triggered_by, created_at
FROM ml_signals
WHERE triggered_by = 'v2_persistence' 
  AND strategy_version = 'v1'
ORDER BY created_at DESC
LIMIT 20;
