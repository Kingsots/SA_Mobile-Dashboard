#!/usr/bin/env python3
"""Check signal generation status after hybrid mode deployment."""

import sqlite3
from datetime import datetime

db = sqlite3.connect('trading_bot.db')
c = db.cursor()

# Signal counts
c.execute('SELECT COUNT(*) FROM ml_signals')
total = c.fetchone()[0]

# By source
c.execute('SELECT triggered_by, COUNT(*) FROM ml_signals GROUP BY triggered_by')
by_source = c.fetchall()

# Latest signals
c.execute('SELECT ticker, confidence, triggered_by, timestamp FROM ml_signals ORDER BY timestamp DESC LIMIT 10')
latest = c.fetchall()

print('=' * 80)
print('📊 HYBRID MODE - SIGNAL GENERATION STATUS')
print('=' * 80)

print(f'\n✅ Total Signals Generated: {total}')

if total == 0:
    print("\n⚠️  NO SIGNALS GENERATED YET!")
    print("This could mean:")
    print("  - Fallback job hasn't run yet (scheduled at :15 UTC each hour)")
    print("  - Event monitor finding no events (expected for low-vol forex)")
    print("  - Service had issues")
    print("\nCheck service status:")
    print("  sudo systemctl status opticore.service")
else:
    print(f'\n📈 By Source:')
    for source, count in by_source:
        emoji = '🟢' if source == 'event_monitor' else '🟡'
        print(f'  {emoji} {source}: {count}')

    print(f'\n📋 Latest 10 Signals:')
    for ticker, conf, source, ts in latest:
        emoji = '🟢' if source == 'event_monitor' else '🟡'
        print(f'  {emoji} {ticker}: conf={conf:.2f}, source={source}')
        print(f'     Time: {ts}')

db.close()
print('\n' + '=' * 80)
