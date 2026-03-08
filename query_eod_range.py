#!/usr/bin/env python3
import sqlite3

db=sqlite3.connect('trading_bot.db')
c=db.cursor()
q = "SELECT id, job_name, status, started_at, completed_at, error_message FROM job_execution_log WHERE job_name='EOD Pipeline (Features + Training)' AND started_at >= '2026-01-30' ORDER BY id DESC"
for r in c.execute(q):
    print(r)
