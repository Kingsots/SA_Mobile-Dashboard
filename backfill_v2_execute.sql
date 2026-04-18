-- Execute the backfill (updates existing mislabeled V2 signals)
UPDATE ml_signals
SET strategy_version = 'v2'
WHERE triggered_by = 'v2_persistence' 
  AND strategy_version = 'v1';

-- Verification After Backfill
SELECT strategy_version, triggered_by, COUNT(*) 
FROM ml_signals
WHERE triggered_by = 'v2_persistence'
GROUP BY strategy_version, triggered_by;
