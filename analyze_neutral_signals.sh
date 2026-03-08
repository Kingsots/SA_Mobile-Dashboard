#!/bin/bash
cd ~/SilentAnalyst

echo "=== DETAILED NEUTRAL SIGNAL ANALYSIS ==="
echo ""
echo "Time window: 2026-02-18 11:57:19 UTC (restart) to now"
echo ""

timeout 5 sqlite3 trading_bot.db << 'SQL'
PRAGMA busy_timeout = 5000;

-- Check distribution of when NEUTRAL signals were created
SELECT 
  'Total NEUTRAL post-restart:' as metric,
  COUNT(*) as value
FROM ml_signals 
WHERE signal=0 AND datetime(timestamp) >= '2026-02-18 11:57:19';

-- First 5 NEUTRAL signals post-restart
SELECT 'First 5 NEUTRAL timestamps:' as type;
SELECT timestamp FROM ml_signals 
WHERE signal=0 AND datetime(timestamp) >= '2026-02-18 11:57:19'
ORDER BY timestamp ASC LIMIT 5;

-- Last 5 NEUTRAL signals post-restart  
SELECT 'Last 5 NEUTRAL timestamps:' as type;
SELECT timestamp FROM ml_signals 
WHERE signal=0 AND datetime(timestamp) >= '2026-02-18 11:57:19'
ORDER BY timestamp DESC LIMIT 5;

-- Check triggered_by column for these NEUTRAL signals
SELECT 
  'NEUTRAL signals by trigger source:' as metric,
  triggered_by,
  COUNT(*) as count
FROM ml_signals 
WHERE signal=0 AND datetime(timestamp) >= '2026-02-18 11:57:19'
GROUP BY triggered_by;
SQL

echo ""
echo "=== ARE THESE BEING WRITTEN BY TIME-BASED FALLBACK? ==="
timeout 5 sqlite3 trading_bot.db << 'SQL'
PRAGMA busy_timeout = 5000;
SELECT COUNT(*) as time_based_fallback_count
FROM ml_signals 
WHERE signal=0 
  AND triggered_by LIKE '%time%' 
  AND datetime(timestamp) >= '2026-02-18 11:57:19';
SQL
