#!/usr/bin/env python3
import sqlite3
from datetime import datetime, timezone

DB='trading_bot.db'
conn=sqlite3.connect(DB)
c=conn.cursor()

# Query latest timestamp per symbol
c.execute("SELECT symbol, MAX(timestamp) FROM ohlcv_data GROUP BY symbol")
rows=c.fetchall()
now=datetime.now(timezone.utc)
rows_out=[]
for symbol, ts in rows:
    parsed=None
    if ts:
        try:
            parsed=datetime.fromisoformat(ts)
        except Exception:
            try:
                parsed=datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
            except Exception:
                parsed=None
    if parsed:
        if parsed.tzinfo is None:
            parsed=parsed.replace(tzinfo=timezone.utc)
        age_minutes=int((now - parsed).total_seconds()/60)
    else:
        age_minutes=None
    rows_out.append((symbol, ts, age_minutes))

# sort by age desc (None last)
rows_out.sort(key=lambda x: (x[2] is None, x[2] if x[2] is not None else -1), reverse=True)

print('Symbol,LastTimestamp,AgeMinutes')
for r in rows_out:
    print(','.join([str(r[0]), str(r[1]), str(r[2])]))

conn.close()
