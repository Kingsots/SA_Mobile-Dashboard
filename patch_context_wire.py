#!/usr/bin/env python3
"""Wire ContextEngine into generate_signals_job() after signal routing loop."""
import shutil, subprocess
from pathlib import Path

FILE = Path("/home/ubuntu/SilentAnalyst/async_scheduler.py")

content = FILE.read_text(encoding="utf-8")
print(f"Read {FILE.name}: {len(content.splitlines())} lines")

all_ok = True

def replace_once(label, old, new):
    global content, all_ok
    if old not in content:
        print(f"  WARN [{label}]: pattern not found")
        all_ok = False
        return
    content = content.replace(old, new, 1)
    print(f"  OK   [{label}]")


CONTEXT_BLOCK = (
    "                    continue\n"
    "        \n"
    "            # ── CONTEXT INTELLIGENCE — per symbol, every run ────────────────\n"
    "            if self.context_engine and symbols:\n"
    "                for symbol in symbols:\n"
    "                    try:\n"
    "                        df = self.signal_engine.get_latest_ohlcv(symbol, interval)\n"
    "                        if df is None or len(df) < 50:\n"
    "                            continue\n"
    "                        df_features = self.feature_engine.compute_all_features(df)\n"
    "                        if df_features is None or df_features.empty:\n"
    "                            continue\n"
    "                        context_state = self.context_engine.compute_context(\n"
    "                            df_features, symbol, interval\n"
    "                        )\n"
    "                        self.db.log_context(\n"
    "                            symbol,\n"
    "                            interval,\n"
    "                            pd.Timestamp(df_features.index[-1]).isoformat(),\n"
    "                            context_state\n"
    "                        )\n"
    "                        logger.debug(\n"
    "                            f\"[CONTEXT] {symbol} {interval} | \"\n"
    "                            f\"comp={context_state.get('compression_score', 0):.2f} \"\n"
    "                            f\"exp={context_state.get('expansion_pressure', 0):.2f} \"\n"
    "                            f\"rsi_stage={context_state.get('rsi_stage', 'UNKNOWN')} \"\n"
    "                            f\"liq_sweep={context_state.get('liquidity_sweep', False)}\"\n"
    "                        )\n"
    "                    except Exception as e:\n"
    "                        logger.warning(f\"[CONTEXT] {symbol} {interval} failed: {e}\")\n"
    "            # ── END CONTEXT ──────────────────────────────────────────────────\n"
    "        \n"
    "        except Exception as e:\n"
    "            logger.error(f\"❌ Signal generation failed: {e}\")\n"
    "            raise"
)

replace_once("context_wire",
    "                    continue\n"
    "        \n"
    "        except Exception as e:\n"
    "            logger.error(f\"❌ Signal generation failed: {e}\")\n"
    "            raise",
    CONTEXT_BLOCK)


print(f"\nResult: {len(content.splitlines())} lines")

if not all_ok:
    print("\nERROR: Pattern not found. File NOT written.")
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
    import shutil
    shutil.copy2(FILE.with_suffix(".py.bak_may3_precontext"), FILE)
    print("Restored.")
    exit(1)

print("\nDone.")
