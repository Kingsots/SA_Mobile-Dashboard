#!/bin/bash
cd ~/SilentAnalyst

echo "======================================================================"
echo "SIGNAL TIMESTAMP ANALYSIS"
echo "======================================================================"
echo ""

echo "Service restart time: 2026-02-18 11:57:19 UTC"
echo ""

echo "=== ML_SIGNALS TABLE STATISTICS ==="
timeout 5 sqlite3 trading_bot.db << 'SQL'
PRAGMA busy_timeout = 5000;
SELECT 
  'Total signals in ml_signals' as metric,
  COUNT(*) as value
FROM ml_signals;

SELECT 
  'Total AFTER restart (11:57:19)' as metric,
  COUNT(*) as value
FROM ml_signals 
WHERE datetime(timestamp) >= '2026-02-18 11:57:19';

SELECT 
  'Total BEFORE restart' as metric,
  COUNT(*) as value
FROM ml_signals 
WHERE datetime(timestamp) < '2026-02-18 11:57:19';

SELECT 
  'Earliest signal timestamp' as metric,
  MIN(timestamp) as value
FROM ml_signals;

SELECT 
  'Latest signal timestamp' as metric,
  MAX(timestamp) as value
FROM ml_signals;
SQL

echo ""
echo "=== SIGNALS IN LAST 8 HOURS (POST-RESTART) ==="
timeout 5 sqlite3 trading_bot.db << 'SQL'
PRAGMA busy_timeout = 5000;
SELECT 
  COUNT(*) as total,
  SUM(CASE WHEN signal=1 THEN 1 ELSE 0 END) as buy_count,
  SUM(CASE WHEN signal=-1 THEN 1 ELSE 0 END) as sell_count,
  SUM(CASE WHEN signal=0 THEN 1 ELSE 0 END) as neutral_count,
  COUNT(DISTINCT ticker) as unique_symbols
FROM ml_signals 
WHERE datetime(timestamp) >= '2026-02-18 11:57:19';
SQL

echo ""
echo "=== FIRST 10 POST-RESTART SIGNALS ==="
timeout 5 sqlite3 -header -column trading_bot.db << 'SQL'
PRAGMA busy_timeout = 5000;
SELECT 
  timestamp,
  ticker,
  interval,
  CASE WHEN signal=1 THEN 'BUY' WHEN signal=-1 THEN 'SELL' ELSE 'NEUTRAL' END as signal,
  ROUND(confidence, 4) as confidence
FROM ml_signals 
WHERE datetime(timestamp) >= '2026-02-18 11:57:19'
ORDER BY timestamp ASC
LIMIT 10;
SQL
