import sqlite3
from pathlib import Path

DB = Path('trading_bot_remote.db')

with sqlite3.connect(DB) as conn:
    cur = conn.cursor()
    max_ts_row = cur.execute("SELECT MAX(timestamp) FROM ml_signals").fetchone()
    latest_ts = max_ts_row[0]
    total = cur.execute("SELECT COUNT(*) FROM ml_signals WHERE timestamp = ?", (latest_ts,)).fetchone()[0]
    tickers = [row[0] for row in cur.execute(
        "SELECT ticker FROM ml_signals WHERE timestamp = ? ORDER BY ticker",
        (latest_ts,)
    )]

print(f"latest_timestamp={latest_ts}")
print(f"signals_at_latest_timestamp={total}")
print(f"tickers={tickers}")
