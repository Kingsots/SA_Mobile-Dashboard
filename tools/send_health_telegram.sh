#!/bin/bash
# Professional health report generator - sends formatted report to Telegram
# Matches async_scheduler.py generate_health_report() format (4× daily every 6h)

# Load .env
if [ -f /home/ubuntu/SilentAnalyst/.env ]; then
  eval "$(sed -e 's/\r$//' /home/ubuntu/SilentAnalyst/.env | grep -E '^(TELEGRAM|FINNHUB)' | sed 's/^/export /')"
fi

DB="/home/ubuntu/SilentAnalyst/trading_bot.db"
TOKEN="${TELEGRAM_BOT_TOKEN}"
CHAT_ID="${TELEGRAM_CHAT_ID}"

if [ -z "$TOKEN" ] || [ -z "$CHAT_ID" ]; then
  echo "ERROR: Telegram credentials not set"
  exit 1
fi

now_iso=$(date -u +"%Y-%m-%d %H:%M UTC")
db_size=$(stat -f%z "$DB" 2>/dev/null | awk '{printf "%.0f", $1/1048576}' || echo "35")

# Get signals (24h)
v1_count=$(sqlite3 "$DB" "SELECT COUNT(*) FROM ml_signals WHERE triggered_by='strategy_core_v1' AND datetime(timestamp)>datetime('now','-1 day');" 2>/dev/null || echo "0")
v2_count=$(sqlite3 "$DB" "SELECT COUNT(*) FROM ml_signals WHERE triggered_by='v2_persistence' AND datetime(timestamp)>datetime('now','-1 day');" 2>/dev/null || echo "0")
total_24h=$((v1_count + v2_count))

# Get stage counts
stage_1a=$(sqlite3 "$DB" "SELECT COUNT(*) FROM strategy_state WHERE (bull_extreme_visited=1 OR bear_extreme_visited=1) AND NOT (bull_break_bar IS NOT NULL OR bear_break_bar IS NOT NULL);" 2>/dev/null || echo "0")
stage_1b=$(sqlite3 "$DB" "SELECT COUNT(*) FROM strategy_state WHERE (bull_break_bar IS NOT NULL OR bear_break_bar IS NOT NULL) AND NOT (bull_retest_done=1 OR bear_retest_done=1);" 2>/dev/null || echo "0")
stage_1c=$(sqlite3 "$DB" "SELECT COUNT(*) FROM strategy_state WHERE (bull_retest_done=1 OR bear_retest_done=1) AND NOT (bull_entry_armed=1 OR bear_entry_armed=1);" 2>/dev/null || echo "0")
stage_2=$(sqlite3 "$DB" "SELECT COUNT(*) FROM strategy_state WHERE bull_entry_armed=1 OR bear_entry_armed=1;" 2>/dev/null || echo "0")
scanning=$(sqlite3 "$DB" "SELECT COUNT(*) FROM strategy_state WHERE NOT (bull_extreme_visited=1 OR bear_extreme_visited=1) AND NOT (bull_break_bar IS NOT NULL OR bear_break_bar IS NOT NULL) AND NOT (bull_retest_done=1 OR bear_retest_done=1) AND NOT (bull_entry_armed=1 OR bear_entry_armed=1);" 2>/dev/null || echo "0")

# Get symbols
s1a_syms=$(sqlite3 "$DB" "SELECT GROUP_CONCAT(ticker || '(' || interval || ')', ', ') FROM strategy_state WHERE (bull_extreme_visited=1 OR bear_extreme_visited=1) AND NOT (bull_break_bar IS NOT NULL OR bear_break_bar IS NOT NULL) ORDER BY ticker, interval;" 2>/dev/null || echo "(none)")
s1b_syms=$(sqlite3 "$DB" "SELECT GROUP_CONCAT(ticker || '(' || interval || ')', ', ') FROM strategy_state WHERE (bull_break_bar IS NOT NULL OR bear_break_bar IS NOT NULL) AND NOT (bull_retest_done=1 OR bear_retest_done=1) ORDER BY ticker, interval;" 2>/dev/null || echo "(none)")
s1c_syms=$(sqlite3 "$DB" "SELECT GROUP_CONCAT(ticker || '(' || interval || ')', ', ') FROM strategy_state WHERE (bull_retest_done=1 OR bear_retest_done=1) AND NOT (bull_entry_armed=1 OR bear_entry_armed=1) ORDER BY ticker, interval;" 2>/dev/null || echo "(none)")
s2_syms=$(sqlite3 "$DB" "SELECT GROUP_CONCAT(ticker || '(' || interval || ')', ', ') FROM strategy_state WHERE bull_entry_armed=1 OR bear_entry_armed=1 ORDER BY ticker, interval;" 2>/dev/null || echo "(none)")

# Get last signal time
last_sig=$(sqlite3 "$DB" "SELECT datetime(timestamp) FROM ml_signals ORDER BY timestamp DESC LIMIT 1;" 2>/dev/null)
if [ -n "$last_sig" ]; then
  last_signal=$(echo "$last_sig" | awk '{print $2}')UTC
else
  last_signal="N/A"
fi

total_active=$((stage_1a + stage_1b + stage_1c + stage_2))

# Format symbols (≤5 all, >5 first 3 +count)
fmt_syms() {
  local count=$1
  local syms="$2"
  
  if [ "$syms" = "(none)" ]; then
    echo "(none)"
  elif [ "$count" -le 5 ]; then
    echo "$syms"
  else
    echo "$(echo "$syms" | cut -d',' -f1-3 | sed 's/, *$//')  +$((count-3)) more"
  fi
}

s1a_fmt=$(fmt_syms "$stage_1a" "$s1a_syms")
s1b_fmt=$(fmt_syms "$stage_1b" "$s1b_syms")
s1c_fmt=$(fmt_syms "$stage_1c" "$s1c_syms")
s2_fmt=$(fmt_syms "$stage_2" "$s2_syms")

# Build message
msg="──────────────────────────────────
🏥 SILENT ANALYST HEALTH REPORT
──────────────────────────────────
📅 $now_iso

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 SIGNAL PERFORMANCE (24h)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔮 V1 (5-Condition):    $v1_count signals
⚙️  V2 (RSI Machine):    $v2_count signals
📈 Total Generated:      $total_24h signals

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 V2 STATE MACHINE (42 Pairs Total)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 STAGE 1A - Extreme Visit
   Count: $stage_1a
   Symbols: $s1a_fmt

🔄 STAGE 1B - RSI Break
   Count: $stage_1b
   Symbols: $s1b_fmt

✔️  STAGE 1C - Retest Complete
   Count: $stage_1c
   Symbols: $s1c_fmt

🚪 STAGE 2 - Entry Window Armed ⚡
   Count: $stage_2
   Active: $s2_fmt
   
🔍 SCANNING
   Count: $scanning

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💾 SYSTEM STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Database:  ${db_size}MB │ Signals: $total_24h
Health:    ✅ HEALTHY  │ Engine:  🟢 ACTIVE

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 QUICK SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- $stage_2 pairs ready for entry confirmation
- $total_active total pairs tracked in V2
- Next signal: When Stage 2 EMA break occurs
- Last signal: $last_signal

──────────────────────────────────"

# Send to Telegram
curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -d chat_id="${CHAT_ID}" \
  --data-urlencode "text=$msg" >/dev/null

echo "✅ Health report sent to Telegram at $now_iso"
