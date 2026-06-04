#!/usr/bin/env python3
"""Phase 1 — Watchlist TTL: 4h → 96h + revalidation logging."""
import shutil, subprocess
from pathlib import Path

FILE = Path("/home/ubuntu/SilentAnalyst/data/daily_scanner.py")

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


# ── 1. REFRESH_HOURS constant: 4 → 96 ────────────────────────────────────────
replace_once("1:REFRESH_HOURS",
    "REFRESH_HOURS = 4",
    "REFRESH_HOURS = 96")


# ── 2. Docstring: update description ─────────────────────────────────────────
replace_once("2:docstring",
    '        expires_at = now + 4 hours\n',
    '        expires_at = now + 96h (rolling TTL; revalidated on each scan)\n')


# ── 3. Replace INSERT OR REPLACE loop with revalidate/add split ───────────────
replace_once("3:upsert_loop",
    "            # Upsert all current watchlist assets\n"
    "            for asset in watchlist:\n"
    "                cursor.execute(\"\"\"\n"
    "                    INSERT OR REPLACE INTO active_watchlist\n"
    "                    (symbol, direction, change_from_open_pct, volume_24h,\n"
    "                     turnover_24h, atr_14_pct, added_at, expires_at, refresh_count)\n"
    "                    VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?,\n"
    "                        COALESCE(\n"
    "                            (SELECT refresh_count + 1 FROM active_watchlist WHERE symbol = ?),\n"
    "                            0\n"
    "                        )\n"
    "                    )\n"
    "                \"\"\", (\n"
    "                    asset[\"symbol\"],\n"
    "                    asset[\"direction\"],\n"
    "                    asset[\"change_from_open_pct\"],\n"
    "                    asset[\"volume_24h\"],\n"
    "                    asset[\"turnover_24h\"],\n"
    "                    asset[\"atr_14_pct\"],\n"
    "                    expires_str,\n"
    "                    asset[\"symbol\"],\n"
    "                ))",
    "            # Revalidate existing / insert new symbols\n"
    "            for asset in watchlist:\n"
    "                sym = asset[\"symbol\"]\n"
    "                cursor.execute(\n"
    "                    \"SELECT symbol FROM active_watchlist WHERE symbol = ?\",\n"
    "                    (sym,)\n"
    "                )\n"
    "                existing = cursor.fetchone()\n"
    "\n"
    "                if existing:\n"
    "                    # Extend TTL; preserve original added_at\n"
    "                    cursor.execute(\"\"\"\n"
    "                        UPDATE active_watchlist\n"
    "                        SET direction = ?, change_from_open_pct = ?,\n"
    "                            volume_24h = ?, turnover_24h = ?,\n"
    "                            atr_14_pct = ?, expires_at = ?,\n"
    "                            refresh_count = refresh_count + 1\n"
    "                        WHERE symbol = ?\n"
    "                    \"\"\", (\n"
    "                        asset[\"direction\"],\n"
    "                        asset[\"change_from_open_pct\"],\n"
    "                        asset[\"volume_24h\"],\n"
    "                        asset[\"turnover_24h\"],\n"
    "                        asset[\"atr_14_pct\"],\n"
    "                        expires_str,\n"
    "                        sym,\n"
    "                    ))\n"
    "                    logger.info(\n"
    "                        f\"[WATCHLIST_REVALIDATE] {sym} — TTL extended to 96h \"\n"
    "                        f\"(expires {expires_str} UTC)\"\n"
    "                    )\n"
    "                else:\n"
    "                    # New symbol — insert with 96h TTL\n"
    "                    cursor.execute(\"\"\"\n"
    "                        INSERT INTO active_watchlist\n"
    "                        (symbol, direction, change_from_open_pct, volume_24h,\n"
    "                         turnover_24h, atr_14_pct, added_at, expires_at, refresh_count)\n"
    "                        VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?, 0)\n"
    "                    \"\"\", (\n"
    "                        sym,\n"
    "                        asset[\"direction\"],\n"
    "                        asset[\"change_from_open_pct\"],\n"
    "                        asset[\"volume_24h\"],\n"
    "                        asset[\"turnover_24h\"],\n"
    "                        asset[\"atr_14_pct\"],\n"
    "                        expires_str,\n"
    "                    ))\n"
    "                    logger.info(\n"
    "                        f\"[WATCHLIST_ADD] {sym} — added with 96h TTL \"\n"
    "                        f\"(expires {expires_str} UTC)\"\n"
    "                    )")


# ── Write & syntax check ──────────────────────────────────────────────────────
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
    shutil.copy2(FILE.with_suffix(".py.bak_may3_pre_phase1"), FILE)
    print("Restored.")
    exit(1)

print("\nDone.")
