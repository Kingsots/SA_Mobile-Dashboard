#!/usr/bin/env python3
import sqlite3
from datetime import datetime, timedelta

db=sqlite3.connect('trading_bot.db')
c=db.cursor()
cutoff=(datetime.utcnow()-timedelta(days=3)).isoformat()
print('Hourly API usage since', cutoff)
q="""
SELECT substr(recorded_at,1,13) as hour, COUNT(*) as reqs
FROM api_usage
WHERE recorded_at >= ?
GROUP BY hour
ORDER BY hour DESC
LIMIT 72
"""
for r in c.execute(q,(cutoff,)):
    print(r)

# Show recent rows
print('\nRecent api_usage rows:')
for r in c.execute('SELECT recorded_at, endpoint, requests FROM api_usage ORDER BY id DESC LIMIT 20'):
    print(r)
