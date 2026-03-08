#!/bin/bash
cd ~/SilentAnalyst
echo "=== Signal Count Test ==="
timeout 5 sqlite3 -cmd "PRAGMA busy_timeout = 5000;" trading_bot.db << 'EOF'
SELECT COUNT(*) as total_signals FROM signals;
EOF
