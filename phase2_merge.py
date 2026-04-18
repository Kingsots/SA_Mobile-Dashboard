#!/usr/bin/env python3
import sqlite3
import sys

SOURCE = "/home/ubuntu/SilentAnalyst/trading_bot_clean.db"   # uploaded local DB
TARGET = "/home/ubuntu/SilentAnalyst/trading_bot.db"         # live SA DB

src = sqlite3.connect(SOURCE)
dst = sqlite3.connect(TARGET)

# Verify strategy_state before touching anything
ss_count = dst.execute("SELECT COUNT(*) FROM strategy_state").fetchone()[0]
print(f"strategy_state records (must be 30): {ss_count}")
if ss_count != 30:
    print("ABORT — strategy_state count wrong. Do not proceed.")
    sys.exit(1)

# Verify context_log before touching anything
cl_count = dst.execute("SELECT COUNT(*) FROM context_log").fetchone()[0]
print(f"context_log records before merge: {cl_count}")

# Pull only the 10 matching columns from source
signals = src.execute("""
    SELECT 
        id, timestamp, ticker, interval, signal, confidence,
        feature_snapshot, model_version, triggered_by, created_at
    FROM ml_signals
    ORDER BY id
""").fetchall()

print(f"Signals to import: {len(signals)}")

dst.execute("BEGIN")
inserted = 0
skipped  = 0

for row in signals:
    try:
        dst.execute("""
            INSERT OR IGNORE INTO ml_signals
            (id, timestamp, ticker, interval, signal, confidence,
             feature_snapshot, model_version, triggered_by, created_at,
             broadcasted)
            VALUES (?,?,?,?,?,?,?,?,?,?,1)
        """, row)
        if dst.execute("SELECT changes()").fetchone()[0] > 0:
            inserted += 1
        else:
            skipped += 1
    except Exception as e:
        print(f"Error on row {row[0]}: {e}")
        skipped += 1

dst.execute("COMMIT")

# Post-merge verification
print(f"\n--- RESULTS ---")
print(f"Inserted: {inserted}")
print(f"Skipped (duplicates): {skipped}")

total = dst.execute("SELECT COUNT(*) FROM ml_signals").fetchone()[0]
rng   = dst.execute("SELECT MIN(timestamp), MAX(timestamp) FROM ml_signals").fetchone()
print(f"Total ml_signals: {total}")
print(f"Date range: {rng[0]} → {rng[1]}")

ss_after = dst.execute("SELECT COUNT(*) FROM strategy_state").fetchone()[0]
cl_after  = dst.execute("SELECT COUNT(*) FROM context_log").fetchone()[0]
print(f"strategy_state after: {ss_after} (must be 30)")
print(f"context_log after: {cl_after} (must be >= {cl_count})")

# Confirm UNIQUE constraint still active
idx = dst.execute("""
    SELECT name, unique FROM pragma_index_list('ml_signals') 
    WHERE name = 'idx_signal_candle_dedup'
""").fetchone()
print(f"UNIQUE constraint: {idx}")

src.close()
dst.close()
