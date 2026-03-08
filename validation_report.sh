#!/bin/bash
cd ~/SilentAnalyst
sleep 2

echo "=============================================================="
echo "HARD GATE - POST-MIGRATION VALIDATION REPORT"
echo "=============================================================="
echo ""

echo "[1] SIGNAL DISTRIBUTION"
echo "------------------------------------------------------------"
timeout 10 sqlite3 -readonly trading_bot.db << EOSQL
SELECT 'Total Signals:', COUNT(*) FROM signals WHERE timestamp >= '2026-02-18 11:57:19';
SELECT 'BUY:', SUM(CASE WHEN signal_type='BUY' THEN 1 ELSE 0 END) FROM signals WHERE timestamp >= '2026-02-18 11:57:19';
SELECT 'SELL:', SUM(CASE WHEN signal_type='SELL' THEN 1 ELSE 0 END) FROM signals WHERE timestamp >= '2026-02-18 11:57:19';
SELECT 'NEUTRAL:', SUM(CASE WHEN signal_type='NEUTRAL' THEN 1 ELSE 0 END) FROM signals WHERE timestamp >= '2026-02-18 11:57:19';
SELECT 'Unique Symbols:', COUNT(DISTINCT symbol) FROM signals WHERE timestamp >= '2026-02-18 11:57:19';
EOSQL

echo ""
echo "[2] CONFIDENCE STATISTICS"
echo "------------------------------------------------------------"
timeout 10 sqlite3 -readonly trading_bot.db << EOSQL
SELECT signal_type, COUNT(*) as cnt, ROUND(AVG(confidence),4) as mean_conf, ROUND(MIN(confidence),4) as min_conf, ROUND(MAX(confidence),4) as max_conf 
FROM signals WHERE timestamp >= '2026-02-18 11:57:19' GROUP BY signal_type;
EOSQL

echo ""
echo "[3] GATE ACTIVITY (from systemd logs)"
echo "------------------------------------------------------------"
GATE_COUNT=$(sudo journalctl -u opticore.service --since '2026-02-18 11:57:19' 2>/dev/null | grep -c 'INFERENCE_GATE' || echo 0)
echo "INFERENCE_GATE triggers: $GATE_COUNT"

echo ""
echo "[4] NaN_TRAP CHECK"
echo "------------------------------------------------------------"
NAN_COUNT=$(sudo journalctl -u opticore.service --since '2026-02-18 11:57:19' 2>/dev/null | grep -c 'NaN_TRAP' || echo 0)
echo "NaN_TRAP triggers: $NAN_COUNT"
if [ "$NAN_COUNT" -eq 0 ]; then
  echo "Status: PASS"
else
  echo "Status: FAIL"
fi

echo ""
echo "[5] SELL RECOVERY CHECK"
echo "------------------------------------------------------------"
timeout 10 sqlite3 -readonly trading_bot.db << EOSQL
SELECT 'SELL appears:', (CASE WHEN COUNT(*) > 0 THEN 'YES' ELSE 'NO' END) FROM signals WHERE signal_type='SELL' AND timestamp >= '2026-02-18 11:57:19';
SELECT 'SELL count:', COUNT(*) FROM signals WHERE signal_type='SELL' AND timestamp >= '2026-02-18 11:57:19';
EOSQL

echo ""
echo "=============================================================="
echo "END REPORT"
echo "=============================================================="
