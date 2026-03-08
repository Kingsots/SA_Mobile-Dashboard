#!/usr/bin/env python3
import sqlite3
from datetime import datetime, timedelta, timezone

# Check signal and training stats
db_path = '/home/ubuntu/opticore-bot/trading_bot.db'
db = sqlite3.connect(db_path)
c = db.cursor()

# Check schema
c.execute("PRAGMA table_info(ml_signals)")
columns = [col[1] for col in c.fetchall()]
print('✅ ML_SIGNALS columns:', ', '.join(columns[:5]))

# Stats
now = datetime.now(timezone.utc)
cutoff_7d = (now - timedelta(days=7)).isoformat()
cutoff_24h = (now - timedelta(days=1)).isoformat()

c.execute('SELECT COUNT(*) FROM ml_signals WHERE timestamp > ?', (cutoff_7d,))
signals_7d = c.fetchone()[0]

c.execute('SELECT COUNT(*) FROM ml_signals WHERE timestamp > ?', (cutoff_24h,))
signals_24h = c.fetchone()[0]

c.execute('SELECT COUNT(*) FROM ml_signals')
total_signals = c.fetchone()[0]

# Latest signal
c.execute('SELECT timestamp, pair FROM ml_signals ORDER BY timestamp DESC LIMIT 1')
latest = c.fetchone()

# Training
c.execute('SELECT COUNT(*) FROM model_training_log WHERE trained_at > ?', (cutoff_7d,))
trainings = c.fetchone()[0]

c.execute('SELECT accuracy, trained_at FROM model_training_log ORDER BY trained_at DESC LIMIT 1')
latest_model = c.fetchone()

db.close()

print(f'\n📊 SIGNAL STATISTICS (This Trading Week Jan 27 - Feb 2)')
print(f'  Signals (7 days):  {signals_7d}')
print(f'  Signals (24 hours): {signals_24h}')
print(f'  All-time signals: {total_signals}')
if latest:
    print(f'  Latest signal: {latest[0]} - {latest[1]}')
else:
    print('  Latest signal: NONE')

print(f'\n📈 MODEL TRAINING')
print(f'  Trainings (7 days): {trainings}')
if latest_model:
    acc, trained = latest_model
    print(f'  Latest model accuracy: {float(acc):.2%}')
    print(f'  Trained at: {trained}')
else:
    print('  Latest model: NONE')
