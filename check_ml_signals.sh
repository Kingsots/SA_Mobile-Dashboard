#!/bin/bash
cd ~/SilentAnalyst
echo "=== Checking ml_signals table (correct table) ==="
timeout 5 sqlite3 -cmd "PRAGMA busy_timeout = 5000;" trading_bot.db << 'EOF'
SELECT 'Total in ml_signals:', COUNT(*) FROM ml_signals;
SELECT 'Latest timestamp:', MAX(timestamp) FROM ml_signals;
SELECT 'count by signal type:', signal, COUNT(*) FROM ml_signals GROUP BY signal;
EOF
