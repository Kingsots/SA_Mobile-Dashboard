#!/usr/bin/env python3
import sqlite3

db=sqlite3.connect('trading_bot.db')
c=db.cursor()
print('\nEOD / Features / Training job run history:')
q = "SELECT id, job_name, status, started_at, completed_at, error_message FROM job_execution_log WHERE job_name LIKE '%EOD%' OR job_name LIKE '%Feature%' OR job_name LIKE '%Training%' ORDER BY id DESC LIMIT 50"
for r in c.execute(q):
    print(r)
