#!/usr/bin/env python3
import sqlite3

DB='trading_bot.db'
conn=sqlite3.connect(DB)
c=conn.cursor()

c.execute("PRAGMA table_info(ohlcv_data)")
cols=c.fetchall()
print('Columns:')
for col in cols:
    print(col)

print('\nSample rows (limit 10):')
try:
    c.execute('SELECT * FROM ohlcv_data LIMIT 10')
    rows=c.fetchall()
    for r in rows:
        print(r)
except Exception as e:
    print('Error reading rows:', e)

conn.close()
