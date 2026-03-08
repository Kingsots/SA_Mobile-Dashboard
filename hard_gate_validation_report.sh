#!/bin/bash
cd ~/SilentAnalyst

echo "======================================================================"
echo "HARD GATE – 1 HOUR POST-MIGRATION REPORT"
echo "======================================================================"
echo ""
echo "Service Restart: 2026-02-18 11:57:19 UTC"
echo "Report Time Window: 11:57:19 to current"
echo ""

echo "[1] SIGNAL DISTRIBUTION"
echo "======================================================================"
timeout 5 sqlite3 trading_bot.db << 'SQL'
PRAGMA busy_timeout = 5000;
SELECT 
  'Total Signals' as metric,
  COUNT(*) as value
FROM ml_signals 
WHERE datetime(timestamp) >= '2026-02-18 11:57:19';

SELECT 
  'BUY Count' as metric,
  COUNT(*) as value
FROM ml_signals 
WHERE signal=1 AND datetime(timestamp) >= '2026-02-18 11:57:19';

SELECT 
  'BUY Percentage' as metric,
  ROUND(100.0 * SUM(CASE WHEN signal=1 THEN 1 ELSE 0 END) / COUNT(*), 1) || '%' as value
FROM ml_signals 
WHERE datetime(timestamp) >= '2026-02-18 11:57:19';

SELECT 
  'SELL Count' as metric,
  COUNT(*) as value
FROM ml_signals 
WHERE signal=-1 AND datetime(timestamp) >= '2026-02-18 11:57:19';

SELECT 
  'SELL Percentage' as metric,
  ROUND(100.0 * SUM(CASE WHEN signal=-1 THEN 1 ELSE 0 END) / COUNT(*), 1) || '%' as value
FROM ml_signals 
WHERE datetime(timestamp) >= '2026-02-18 11:57:19';

SELECT 
  'NEUTRAL Count' as metric,
  COUNT(*) as value
FROM ml_signals 
WHERE signal=0 AND datetime(timestamp) >= '2026-02-18 11:57:19';

SELECT 
  'NEUTRAL Percentage' as metric,
  ROUND(100.0 * SUM(CASE WHEN signal=0 THEN 1 ELSE 0 END) / COUNT(*), 1) || '%' as value
FROM ml_signals 
WHERE datetime(timestamp) >= '2026-02-18 11:57:19';

SELECT 
  'Unique Symbols' as metric,
  COUNT(DISTINCT ticker) as value
FROM ml_signals 
WHERE datetime(timestamp) >= '2026-02-18 11:57:19';

SELECT 
  'Unique Intervals' as metric,
  COUNT(DISTINCT interval) as value
FROM ml_signals 
WHERE datetime(timestamp) >= '2026-02-18 11:57:19';
SQL

echo ""
echo "[2] CONFIDENCE BY CLASS"
echo "======================================================================"
timeout 5 sqlite3 trading_bot.db << 'SQL'
PRAGMA busy_timeout = 5000;
SELECT 
  CASE WHEN signal=1 THEN 'BUY'
       WHEN signal=-1 THEN 'SELL'
       ELSE 'NEUTRAL' END as class,
  'Mean Confidence' as metric,
  ROUND(AVG(confidence), 4) as value
FROM ml_signals
WHERE datetime(timestamp) >= '2026-02-18 11:57:19'
GROUP BY signal;

SELECT 
  CASE WHEN signal=1 THEN 'BUY'
       WHEN signal=-1 THEN 'SELL'
       ELSE 'NEUTRAL' END as class,
  'Min Confidence' as metric,
  ROUND(MIN(confidence), 4) as value
FROM ml_signals
WHERE datetime(timestamp) >= '2026-02-18 11:57:19'
GROUP BY signal;

SELECT 
  CASE WHEN signal=1 THEN 'BUY'
       WHEN signal=-1 THEN 'SELL'
       ELSE 'NEUTRAL' END as class,
  'Max Confidence' as metric,
  ROUND(MAX(confidence), 4) as value
FROM ml_signals
WHERE datetime(timestamp) >= '2026-02-18 11:57:19'
GROUP BY signal;
SQL

echo ""
echo "[3] GATE ACTIVITY"
echo "======================================================================"
GATE_COUNT=$(sudo journalctl -u opticore.service --since '2026-02-18 11:57:19' 2>/dev/null | grep -c '\[INFERENCE_GATE\]' || echo 0)
echo "Total Gate Triggers: $GATE_COUNT"

echo ""
echo "Top 5 Symbols Gated:"
sudo journalctl -u opticore.service --since '2026-02-18 11:57:19' 2>/dev/null | grep '\[INFERENCE_GATE\]' | grep -oP '(?<=\[INFERENCE_GATE\]\s)\w+' | sort | uniq -c | sort -rn | head -5 || echo "No gate data"

TOTAL_SIGNALS=$(sqlite3 trading_bot.db "SELECT COUNT(*) FROM ml_signals WHERE datetime(timestamp) >= '2026-02-18 11:57:19';")
GATE_RATE=$(echo "scale=1; 100 * $GATE_COUNT / ($TOTAL_SIGNALS + $GATE_COUNT)" | bc 2>/dev/null || echo "N/A")
echo ""
echo "Gate Trigger Rate: $GATE_RATE%"

echo ""
echo "[4] NaN_TRAP CHECK"
echo "======================================================================"
NAN_COUNT=$(sudo journalctl -u opticore.service --since '2026-02-18 11:57:19' 2>/dev/null | grep -c '\[NaN_TRAP\]' || echo 0)
echo "NaN_TRAP Count: $NAN_COUNT"
if [ "$NAN_COUNT" -eq 0 ]; then
  echo "Status: PASS ✓"
else
  echo "Status: FAIL ✗"
fi

echo ""
echo "[5] SELL RECOVERY CHECK"
echo "======================================================================"
timeout 5 sqlite3 trading_bot.db << 'SQL'
PRAGMA busy_timeout = 5000;
SELECT 
  CASE WHEN COUNT(*) > 0 THEN 'YES' ELSE 'NO' END as 'SELL Appears'
FROM ml_signals 
WHERE signal=-1 AND datetime(timestamp) >= '2026-02-18 11:57:19';

SELECT 
  COUNT(*) as 'SELL Count'
FROM ml_signals 
WHERE signal=-1 AND datetime(timestamp) >= '2026-02-18 11:57:19';

SELECT 
  ROUND(100.0 * SUM(CASE WHEN signal=-1 THEN 1 ELSE 0 END) / COUNT(*), 1) || '%' as 'SELL Percentage'
FROM ml_signals 
WHERE datetime(timestamp) >= '2026-02-18 11:57:19';
SQL

SELL_PCT=$(sqlite3 trading_bot.db "SELECT ROUND(100.0 * SUM(CASE WHEN signal=-1 THEN 1 ELSE 0 END) / COUNT(*), 1) FROM ml_signals WHERE datetime(timestamp) >= '2026-02-18 11:57:19';")

if [ -z "$SELL_PCT" ] || [ "$SELL_PCT" == "0" ]; then
  SELL_IN_RANGE="NO - 0% is outside 20-60% range"
elif (( $(echo "$SELL_PCT >= 20 && $SELL_PCT <= 60" | bc -l) )); then
  SELL_IN_RANGE="YES - $SELL_PCT% is within 20-60% range"
else
  SELL_IN_RANGE="NO - $SELL_PCT% is outside 20-60% range"
fi

echo ""
echo "SELL Within 20-60% Range: $SELL_IN_RANGE"

echo ""
echo "======================================================================"
echo "END REPORT"
echo "======================================================================"
