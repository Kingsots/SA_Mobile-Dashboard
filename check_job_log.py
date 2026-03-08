#!/usr/bin/env python3
import sqlite3

db=sqlite3.connect('trading_bot.db')
c=db.cursor()
print('PRAGMA table_info(job_execution_log)')
for r in c.execute("PRAGMA table_info(job_execution_log)"):
    print(r)
print('\nRecent rows:')
for r in c.execute('SELECT id, job_name, status, started_at, completed_at, duration_seconds, error_message FROM job_execution_log ORDER BY id DESC LIMIT 20'):
    print(r)
