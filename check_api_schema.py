#!/usr/bin/env python3
import sqlite3

db=sqlite3.connect('trading_bot.db')
c=db.cursor()
print('PRAGMA table_info(api_usage)')
for r in c.execute("PRAGMA table_info(api_usage)"):
    print(r)

print('\nSample rows:')
for r in c.execute('SELECT * FROM api_usage ORDER BY id DESC LIMIT 20'):
    print(r)
