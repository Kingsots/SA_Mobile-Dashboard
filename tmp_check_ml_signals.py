import sqlite3
from pathlib import Path

DB_PATH = Path('data/trading_bot.db')

try:
	conn = sqlite3.connect(DB_PATH)
	cur = conn.cursor()
	cur.execute("SELECT COUNT(1) FROM ml_signals WHERE timestamp NOT LIKE '%T%'")
	count = cur.fetchone()[0]
	msg = f"corrupted_rows={count}\n"
	print(msg, end="")
	Path("tmp_count.txt").write_text(msg, encoding="utf-8")
except Exception as exc:
	print(f"error={exc!r}")
finally:
	try:
		conn.close()
	except Exception:
		pass
