#!/bin/bash
cd ~/SilentAnalyst
echo "=== Total Signals in DB ==="
timeout 10 sqlite3 -readonly trading_bot.db "SELECT COUNT(*) FROM signals;"
echo ""
echo "=== Latest Timestamp ==="
timeout 10 sqlite3 -readonly trading_bot.db "SELECT MAX(timestamp) FROM signals;"
echo ""
echo "=== Signals by Type ==="
timeout 10 sqlite3 -readonly trading_bot.db "SELECT signal_type, COUNT(*) FROM signals GROUP BY signal_type;"
echo ""
echo "=== Service Status ==="
sudo systemctl status opticore.service | grep -E "(Active:|running|PID)"
