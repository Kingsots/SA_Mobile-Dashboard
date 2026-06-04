#!/usr/bin/env python3
"""Remove remaining STRATEGY_V2_AVAILABLE print/log lines."""
import shutil, subprocess
from pathlib import Path

FILE = Path("/home/ubuntu/SilentAnalyst/signals/xgb_signal_engine_ec2.py")

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


# __init__ print block: remove V2 line
replace_once("init_v2_print",
    '        print(f"   V1 Available: {STRATEGY_V1_AVAILABLE}")\n'
    '        print(f"   V2 Available: {STRATEGY_V2_AVAILABLE}")\n'
    '        print(f"   V3 Available: {STRATEGY_V3_AVAILABLE}")\n',
    '        print(f"   V1 Available: {STRATEGY_V1_AVAILABLE}")\n'
    '        print(f"   V3 Available: {STRATEGY_V3_AVAILABLE}")\n')

# generate_signals header: remove V2 print + update log
replace_once("gen_v2_print",
    '        print(f"  V1 Available: {STRATEGY_V1_AVAILABLE}")\n'
    '        print(f"  V2 Available: {STRATEGY_V2_AVAILABLE}")\n',
    '        print(f"  V1 Available: {STRATEGY_V1_AVAILABLE}")\n')

replace_once("gen_v2_log",
    '        signal_logger.info(f"Strategies: V1={STRATEGY_V1_AVAILABLE}, V2={STRATEGY_V2_AVAILABLE}")\n',
    '        signal_logger.info(f"Strategies: V1={STRATEGY_V1_AVAILABLE}")\n')

# Also update the header print label
replace_once("gen_header_label",
    '        print(f"  \U0001f52e DUAL STRATEGY SIGNAL GENERATION - {interval}")\n',
    '        print(f"  \U0001f52e SIGNAL GENERATION - {interval}")\n')


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
    exit(1)

print("\nDone.")
