#!/usr/bin/env python3
"""Change 5: Disable V3 session filter by default in strategy_core_v3_prod.py."""
import shutil, subprocess
from pathlib import Path

FILE = Path("/home/ubuntu/SilentAnalyst/core/strategy_core_v3_prod.py")
BACKUP = FILE.with_suffix(".py.bak_may3_c5")

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


print("\n=== Change 5: Disable V3 session filter ===")

# 5a: Add session_filter_enabled field to V3Config (after session_end_utc)
replace_once("5a:session_filter_field",
    "    # ── Session filter (UTC hours, inclusive)\n"
    "    session_start_utc:    int   = 7\n"
    "    session_end_utc:      int   = 20\n",
    "    # ── Session filter (UTC hours, inclusive)\n"
    "    session_start_utc:    int   = 7\n"
    "    session_end_utc:      int   = 20\n"
    "    session_filter_enabled: bool = False  # disabled for 24/7 crypto\n")

# 5b: Wrap session check in _process_bar with the flag
replace_once("5b:session_check_wrap",
    "        # Session filter\n"
    "        if not cr.in_session:\n"
    "            return SignalResult(stage=self.stage, reason=\"Outside session\")\n",
    "        # Session filter\n"
    "        if self.cfg.session_filter_enabled and not cr.in_session:\n"
    "            return SignalResult(stage=self.stage, reason=\"Outside session\")\n")


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
