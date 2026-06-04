#!/usr/bin/env python3
"""Changes 1, 2, 4 in xgb_signal_engine_ec2.py."""
import shutil, subprocess
from pathlib import Path

FILE = Path("/home/ubuntu/SilentAnalyst/signals/xgb_signal_engine_ec2.py")
BACKUP = FILE.with_suffix(".py.bak_may3_c1c2c4")

content = FILE.read_text(encoding="utf-8")
print(f"Read {FILE.name}: {len(content.splitlines())} lines")

if not BACKUP.exists():
    shutil.copy2(FILE, BACKUP)
    print(f"Backup -> {BACKUP.name}")
else:
    print(f"Backup already exists: {BACKUP.name}")

all_ok = True

def replace_once(label, old, new):
    global content, all_ok
    if old not in content:
        print(f"  WARN [{label}]: pattern not found")
        all_ok = False
        return
    content = content.replace(old, new, 1)
    print(f"  OK   [{label}]")

def remove(label, start, end, replacement=""):
    global content, all_ok
    si = content.find(start)
    if si == -1:
        print(f"  WARN [{label}]: start not found: {start[:60]!r}")
        all_ok = False
        return
    ei = content.find(end, si)
    if ei == -1:
        print(f"  WARN [{label}]: end not found: {end[:60]!r}")
        all_ok = False
        return
    ei += len(end)
    n = content[si:ei].count('\n')
    content = content[:si] + replacement + content[ei:]
    print(f"  OK   [{label}]: -{n} lines")

def remove_line(label, pattern):
    """Remove the first line containing pattern."""
    global content, all_ok
    idx = content.find(pattern)
    if idx == -1:
        print(f"  WARN [{label}]: line not found: {pattern[:60]!r}")
        all_ok = False
        return
    sol = content.rfind('\n', 0, idx) + 1
    eol = content.find('\n', idx)
    if eol == -1:
        eol = len(content) - 1
    content = content[:sol] + content[eol + 1:]
    print(f"  OK   [{label}]")


print("\n=== Change 1: TelegramBot -> private bot ===")
replace_once("1:telegram_private_bot",
    "        try:\n"
    "            self.telegram_bot = TelegramBot()\n"
    "        except Exception as e:\n"
    "            logging.warning(f\"Telegram initialization failed: {e}\")\n"
    "            self.telegram_bot = None",
    "        try:\n"
    "            self.telegram_bot = TelegramBot(\n"
    "                token=Config.PRIVATE_BOT_TOKEN,\n"
    "                chat_id=Config.PRIVATE_BOT_CHAT_ID,\n"
    "            )\n"
    "        except Exception as e:\n"
    "            logging.warning(f\"Telegram initialization failed: {e}\")\n"
    "            self.telegram_bot = None")


print("\n=== Change 2: Strip V2 ===")

# 2a: Remove V2 import block
remove("2a:v2_import_block",
    "\ntry:\n    from core.strategy_core_v2 import evaluate as evaluate_v2\n",
    "    logging.error(f\"Failed to import strategy_core_v2: {e}\")\n")

# 2b: Remove V2 elif in _evaluate_strategy
replace_once("2b:v2_elif",
    "        elif strategy_name == 'strategy_core_v2':\n"
    "            if not STRATEGY_V2_AVAILABLE:\n"
    "                logging.error(f\"Strategy V2 not available for {ticker}-{interval}\")\n"
    "                return None\n"
    "            evaluator = evaluate_v2\n"
    "        elif strategy_name == 'strategy_core_v3':\n",
    "        elif strategy_name == 'strategy_core_v3':\n")

# 2c: Simplify confidence to 1.0
replace_once("2c:confidence",
    "            confidence=0.95 if strategy_name == 'strategy_core_v2' else 1.0,",
    "            confidence=1.0,")

# 2d: Remove V2 block in generate_signals() per-symbol loop
remove("2d:v2_per_symbol_block",
    "\n            if STRATEGY_V2_AVAILABLE:\n"
    "                # Optional: Skip V2 if V1 already found signal (V1-first mode)\n",
    "                    signal_logger.debug(f\"{symbol:10} | V2 SKIPPED (V1-first mode: V1 already signaled)\")\n")

# 2e: Remove v2_buy/v2_sell sum vars (individual lines - avoids emoji matching issues)
remove_line("2e:v2_buy_sum",
    "        v2_buy = sum(1 for s in signals if s.get('source') == 'strategy_core_v2'")
remove_line("2e:v2_sell_sum",
    "        v2_sell = sum(1 for s in signals if s.get('source') == 'strategy_core_v2'")
remove_line("2e:v2_print",
    "        print(f\"  [V2] ")
remove_line("2e:v2_log",
    "        signal_logger.info(f\"V2: BUY=")

# 2f: Remove v2_buy/v2_sell from event_debug counts dict
replace_once("2f:v2_event_debug_counts",
    "                'counts': {\n"
    "                    'total': len(signals),\n"
    "                    'v1_buy': v1_buy,\n"
    "                    'v1_sell': v1_sell,\n"
    "                    'v2_buy': v2_buy,\n"
    "                    'v2_sell': v2_sell,\n"
    "                },",
    "                'counts': {\n"
    "                    'total': len(signals),\n"
    "                    'v1_buy': v1_buy,\n"
    "                    'v1_sell': v1_sell,\n"
    "                },")

# 2g: Remove handle_event V2 block
remove("2g:handle_event_v2_block",
    "\n        if STRATEGY_V2_AVAILABLE:\n"
    "            # V2: Use stateful engine for persistent RSI sequence tracking\n",
    "                logging.error(f\"[V2_STATEFUL] Error processing event for {event.ticker}-{event.interval}: {e}\")\n")


print("\n=== Change 4: Fix V3 unpack + activate + broadcast ===")
remove("4:v3_block",
    "            try:\n"
    "                # Evaluate V3 strategy (logging-only, no trading)\n",
    "                logging.error(f\"[V3] Evaluation error for {ticker}-{interval}: {e}\")\n"
    "                return None\n",
    "            try:\n"
    "                # Evaluate V3 strategy\n"
    "                v3_result = v3_engine.evaluate(df_ohlcv)\n"
    "                v3_score = v3_result.score\n"
    "                v3_direction = v3_result.signal\n"
    "                v3_tags = v3_result.confirmation_tags or []\n"
    "\n"
    "                logging.info(\n"
    "                    f\"[V3] {ticker}-{interval} | \"\n"
    "                    f\"Score: {v3_score}/8 | Direction: {v3_direction} | \"\n"
    "                    f\"Tags: {v3_tags}\"\n"
    "                )\n"
    "\n"
    "                if v3_direction != 0:\n"
    "                    direction_label = \"BUY\" if v3_direction == 1 else \"SELL\"\n"
    "                    v3_signal_data = {\n"
    "                        'ticker': ticker,\n"
    "                        'interval': interval,\n"
    "                        'signal': v3_direction,\n"
    "                        'signal_label': direction_label,\n"
    "                        'confidence': 1.0,\n"
    "                        'source': 'strategy_core_v3',\n"
    "                        'score': v3_score,\n"
    "                        'confirmation_tags': v3_tags,\n"
    "                        'entry_price': v3_result.entry_price,\n"
    "                        'stop_loss': v3_result.sl,\n"
    "                        'take_profit': v3_result.tp,\n"
    "                        'risk_reward': v3_result.rr,\n"
    "                        'timestamp': datetime.now(timezone.utc).isoformat(),\n"
    "                    }\n"
    "                    try:\n"
    "                        self.save_signal(v3_signal_data)\n"
    "                    except Exception as e:\n"
    "                        logging.error(f\"[V3] Failed to save signal: {e}\")\n"
    "\n"
    "                    if self.telegram_bot is not None:\n"
    "                        try:\n"
    "                            tag_str = ' | '.join(v3_tags) if v3_tags else 'none'\n"
    "                            entry_str = f\"{v3_result.entry_price:.5f}\" if v3_result.entry_price else \"N/A\"\n"
    "                            sl_str = f\"{v3_result.sl:.5f}\" if v3_result.sl else \"N/A\"\n"
    "                            tp_str = f\"{v3_result.tp:.5f}\" if v3_result.tp else \"N/A\"\n"
    "                            rr_str = f\"{v3_result.rr:.2f}\" if v3_result.rr else \"N/A\"\n"
    "                            v3_msg = (\n"
    "                                f\"\U0001f3d7 *V3 Structure Signal*\\n\"\n"
    "                                f\"*{ticker}* {interval} — *{direction_label}*\\n\"\n"
    "                                f\"Score: {v3_score}/8\\n\"\n"
    "                                f\"Tags: {tag_str}\\n\"\n"
    "                                f\"Entry: {entry_str} | SL: {sl_str} | TP: {tp_str} | RR: {rr_str}\"\n"
    "                            )\n"
    "                            self.telegram_bot.send_message(v3_msg)\n"
    "                        except Exception as e:\n"
    "                            logging.error(f\"[V3] Telegram broadcast failed: {e}\")\n"
    "\n"
    "                return None\n"
    "\n"
    "            except Exception as e:\n"
    "                logging.error(f\"[V3] Evaluation error for {ticker}-{interval}: {e}\")\n"
    "                return None\n"
)


print(f"\nResult: {len(content.splitlines())} lines")

if not all_ok:
    print("\nERROR: Some patterns not found. File NOT written.")
    exit(1)

FILE.write_text(content, encoding="utf-8")
print(f"Written: {FILE}")

result = subprocess.run(
    ["python3", "-m", "py_compile", str(FILE)],
    capture_output=True, text=True
)
if result.returncode == 0:
    print("Syntax OK")
else:
    print(f"Syntax error:\n{result.stderr}")
    print("Restoring backup...")
    shutil.copy2(BACKUP, FILE)
    print("Restored.")
    exit(1)

print("\nDone.")
