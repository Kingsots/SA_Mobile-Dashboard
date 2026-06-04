#!/usr/bin/env python3
"""Change 3: Strip V2ExecutionEngine from async_scheduler.py."""
import shutil, subprocess
from pathlib import Path

FILE = Path("/home/ubuntu/SilentAnalyst/async_scheduler.py")
BACKUP = FILE.with_suffix(".py.bak_may3_c3")

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


print("\n=== Change 3: Strip V2ExecutionEngine ===")

# 3a: Remove import line
replace_once("3a:v2_import",
    "from signals.v2_execution_engine import V2ExecutionEngine\n",
    "")

# 3b: Remove instantiation line
replace_once("3b:v2_instantiation",
    "\n        self.v2_execution_engine = V2ExecutionEngine()",
    "")

# 3c: Remove enrichment block
remove("3c:v2_enrichment_block",
    "\n            # NEW: Enrich V1 signals with V2 execution data (real-time entry/SL/TP)\n"
    "            if Config.V2_EXECUTION_ENABLED and len(actionable) > 0:\n",
    "            logger.info(f\"✅ V2 execution enrichment complete: {len(actionable)} signals enriched\")\n")


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
