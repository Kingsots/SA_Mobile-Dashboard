#!/usr/bin/env python3
import sqlite3
import os
from datetime import datetime, timedelta

# Base date provided by user
base_dt = datetime(2026,2,17,11,4)

# compute cutoff for 20 trading days prior to base_dt (count weekdays Mon-Fri)
def cutoff_for_trading_days(base, trading_days=20):
    d = base.date()
    count = 0
    while count < trading_days:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            count += 1
    # use start of that day as cutoff
    return datetime(d.year, d.month, d.day)

cutoff_dt = cutoff_for_trading_days(base_dt, trading_days=20)
cutoff_iso = cutoff_dt.isoformat()

candidates = [
    'trading_bot.db',
    'tradingbot.db',
    'trading_bot_remote.db',
    'ml_signals.db',
    '1trading_bot.db',
    'trading_bot_old.db',
    'trading_bot_remote.db'
]

cwd = os.getcwd()
print('Working dir:', cwd)
print('Using base datetime:', base_dt.isoformat())
print('Cutoff (20 trading days back):', cutoff_iso)
print('')

for name in candidates:
    path = os.path.join(cwd, name)
    if not os.path.exists(path):
        continue
    print('DB:', path)
    try:
        conn = sqlite3.connect(path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ml_signals'")
        if not c.fetchone():
            print('  - no table `ml_signals`')
            conn.close()
            continue
        # schema
        print('  - ml_signals schema:')
        for r in c.execute("PRAGMA table_info(ml_signals)"):
            print('    ', r)
        # totals
        c.execute('SELECT COUNT(*) FROM ml_signals')
        total = c.fetchone()[0]
        print(f'  - total rows: {total}')
        # latest timestamp
        try:
            c.execute("SELECT timestamp FROM ml_signals ORDER BY timestamp DESC LIMIT 1")
            latest = c.fetchone()
            latest_ts = latest[0] if latest else None
            print('  - latest timestamp:', latest_ts)
        except Exception as e:
            print('  - could not retrieve latest timestamp:', e)
        # count since cutoff
        try:
            c.execute('SELECT COUNT(*) FROM ml_signals WHERE timestamp >= ?', (cutoff_iso,))
            cnt = c.fetchone()[0]
            print(f'  - rows since cutoff ({cutoff_iso}): {cnt}')
        except Exception as e:
            print('  - could not count since cutoff:', e)
        # show last 20 rows
        print('  - last 20 rows (most recent first):')
        try:
            for row in c.execute('SELECT * FROM ml_signals ORDER BY timestamp DESC LIMIT 20'):
                print('    ', row)
        except Exception as e:
            print('    - could not fetch rows:', e)
        conn.close()
    except Exception as e:
        print('  - error opening DB:', e)
    print('')

print('Done.')
