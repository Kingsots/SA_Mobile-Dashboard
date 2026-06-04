#!/bin/bash
# Simple V2 state queries using sqlite3 (no Python dependencies)
DB="/home/ubuntu/SilentAnalyst/trading_bot.db"

echo "V2 SIGNALS:"
sqlite3 -header -column "$DB" "SELECT COUNT(*) AS total_v2_signals FROM ml_signals WHERE triggered_by='v2_persistence';"

echo
echo "ENTRY WINDOW STATES:"
sqlite3 -header -column "$DB" "SELECT ticker, interval, bull_entry_window_bar, bear_entry_window_bar, last_updated FROM strategy_state WHERE bull_entry_armed=1 OR bear_entry_armed=1;"

echo
echo "STAGE SUMMARY:"
sqlite3 -header -column "$DB" "SELECT 'Stage 2 (Entry Window)' as stage, COALESCE(COUNT(*),0) as count FROM strategy_state WHERE bull_entry_armed=1 OR bear_entry_armed=1
UNION ALL
SELECT 'Stage 1C (Retest Done)', COALESCE(COUNT(*),0) FROM strategy_state WHERE (bull_retest_done=1 OR bear_retest_done=1) AND NOT (bull_entry_armed=1 OR bear_entry_armed=1)
UNION ALL
SELECT 'Stage 1B (Break)', COALESCE(COUNT(*),0) FROM strategy_state WHERE (bull_break_bar IS NOT NULL OR bear_break_bar IS NOT NULL) AND NOT (bull_retest_done=1 OR bear_retest_done=1)
UNION ALL
SELECT 'Stage 1A (Extreme)', COALESCE(COUNT(*),0) FROM strategy_state WHERE (bull_extreme_visited=1 OR bear_extreme_visited=1) AND NOT (bull_break_bar IS NOT NULL OR bear_break_bar IS NOT NULL)
UNION ALL
SELECT 'Scanning', COALESCE(COUNT(*),0) FROM strategy_state WHERE NOT (bull_extreme_visited=1 OR bear_extreme_visited=1);"
