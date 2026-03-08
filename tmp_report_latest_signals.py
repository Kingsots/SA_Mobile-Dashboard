import sqlite3
from pathlib import Path

def main(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        latest = cur.execute("SELECT MAX(timestamp) FROM ml_signals").fetchone()[0]
        rows = cur.execute(
            "SELECT ticker FROM ml_signals WHERE timestamp = ? ORDER BY ticker",
            (latest,)
        ).fetchall()
        recent_rows = cur.execute(
            "SELECT ticker, timestamp FROM ml_signals ORDER BY timestamp DESC, ticker ASC LIMIT 20"
        ).fetchall()
    tickers = [row[0] for row in rows]
    print(f"latest_timestamp={latest}")
    print(f"signals_at_latest_timestamp={len(tickers)}")
    print(f"tickers={tickers}")
    print("recent_rows=")
    for ticker, ts in recent_rows:
        print(f"  {ticker:7} {ts}")


if __name__ == "__main__":
    main(Path("data/trading_bot.db"))
