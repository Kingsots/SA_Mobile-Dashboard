#!/usr/bin/env python3
"""
Event-driven signals bias report (20 trading days)
- Only signals where triggered_by LIKE 'event:%'
- No pandas/matplotlib - pure CSV output + summary
"""
import argparse
import sqlite3
from datetime import datetime, timedelta, timezone
import csv
import os

parser = argparse.ArgumentParser(description='Event-driven signal bias report')
parser.add_argument('--db', default='trading_bot.db', help='Path to trading_bot.db')
parser.add_argument('--days', type=int, default=20, help='Lookback window in trading days')
parser.add_argument('--outdir', default='reports/event_signals_bias', help='Output folder')
args = parser.parse_args()

os.makedirs(args.outdir, exist_ok=True)

# Calculate cutoff for 20 trading days
base_dt = datetime.now(timezone.utc)
d = base_dt.date()
count = 0
while count < args.days:
    d -= timedelta(days=1)
    if d.weekday() < 5:
        count += 1
cutoff_dt = datetime(d.year, d.month, d.day)
cutoff_iso = cutoff_dt.isoformat()

conn = sqlite3.connect(args.db)
c = conn.cursor()

# Query event-driven signals
c.execute("""
    SELECT id, timestamp, ticker, interval, signal, confidence, model_version, triggered_by 
    FROM ml_signals 
    WHERE triggered_by LIKE 'event:%' AND timestamp >= ?
    ORDER BY timestamp DESC
""", (cutoff_iso,))

rows = c.fetchall()

if not rows:
    print(f'No event-driven signals found in the last {args.days} trading days.')
    conn.close()
    raise SystemExit(0)

print(f'✅ Found {len(rows)} event-driven signals since {cutoff_iso}')

# Save raw signals to CSV
with open(os.path.join(args.outdir, 'event_signals_raw_20trading.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['id', 'timestamp', 'ticker', 'interval', 'signal', 'confidence', 'model_version', 'triggered_by'])
    w.writerows(rows)

# Signal distribution
signal_counts = {}
ticker_signal_counts = {}
daily_counts = {}
event_type_counts = {}

signal_map = {1: 'buy', -1: 'sell', 0: 'neutral'}

for row in rows:
    _, timestamp, ticker, _, signal, _, _, event_type = row
    signal_label = signal_map.get(signal, 'unknown')
    day = timestamp.split('T')[0]
    
    signal_counts[signal_label] = signal_counts.get(signal_label, 0) + 1
    
    if ticker not in ticker_signal_counts:
        ticker_signal_counts[ticker] = {'buy': 0, 'sell': 0, 'neutral': 0}
    ticker_signal_counts[ticker][signal_label] += 1
    
    if day not in daily_counts:
        daily_counts[day] = {'buy': 0, 'sell': 0, 'neutral': 0}
    daily_counts[day][signal_label] += 1
    
    event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1

# Signal counts CSV
with open(os.path.join(args.outdir, 'event_signal_counts_20trading.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['signal', 'count'])
    for signal, count in sorted(signal_counts.items()):
        w.writerow([signal, count])

print('\n📊 Signal distribution (event-driven):')
for signal, count in sorted(signal_counts.items()):
    print(f'  {signal}: {count}')

# Daily counts CSV
with open(os.path.join(args.outdir, 'event_daily_signal_counts.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['day', 'buy', 'sell', 'neutral', 'total'])
    for day in sorted(daily_counts.keys(), reverse=True):
        counts = daily_counts[day]
        total = counts['buy'] + counts['sell'] + counts['neutral']
        w.writerow([day, counts['buy'], counts['sell'], counts['neutral'], total])

print('\n📅 Daily counts (top 10):')
for day in sorted(daily_counts.keys(), reverse=True)[:10]:
    counts = daily_counts[day]
    total = counts['buy'] + counts['sell'] + counts['neutral']
    print(f'  {day}: buy={counts["buy"]} sell={counts["sell"]} total={total}')

# Per-symbol bias CSV
with open(os.path.join(args.outdir, 'event_per_symbol_bias.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['ticker', 'buy', 'sell', 'neutral', 'total', 'pct_buy'])
    
    sorted_tickers = sorted(ticker_signal_counts.items(), 
                           key=lambda x: x[1]['buy'] / (x[1]['buy'] + x[1]['sell'] + x[1]['neutral']) if (x[1]['buy'] + x[1]['sell'] + x[1]['neutral']) > 0 else 0,
                           reverse=True)
    
    for ticker, counts in sorted_tickers:
        total = counts['buy'] + counts['sell'] + counts['neutral']
        pct_buy = (counts['buy'] / total * 100) if total > 0 else 0
        w.writerow([ticker, counts['buy'], counts['sell'], counts['neutral'], total, f"{pct_buy:.1f}"])

print('\n🎯 Top 15 symbols by %BUY (event-driven):')
for ticker, counts in sorted(ticker_signal_counts.items(), 
                             key=lambda x: x[1]['buy'] / (x[1]['buy'] + x[1]['sell'] + x[1]['neutral']) if (x[1]['buy'] + x[1]['sell'] + x[1]['neutral']) > 0 else 0,
                             reverse=True)[:15]:
    total = counts['buy'] + counts['sell'] + counts['neutral']
    pct_buy = (counts['buy'] / total * 100) if total > 0 else 0
    print(f'  {ticker}: {pct_buy:.1f}% buy (n={total})')

# Event type distribution CSV
with open(os.path.join(args.outdir, 'event_type_distribution.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['event_type', 'count'])
    for event_type in sorted(event_type_counts.keys(), key=lambda x: event_type_counts[x], reverse=True):
        w.writerow([event_type, event_type_counts[event_type]])

print('\n⚡ Event type distribution:')
for event_type in sorted(event_type_counts.keys(), key=lambda x: event_type_counts[x], reverse=True):
    count = event_type_counts[event_type]
    pct = (count / len(rows) * 100)
    print(f'  {event_type}: {count} ({pct:.1f}%)')

conn.close()

print(f'\n✅ Report generated in {args.outdir}')
print('CSVs created:')
print('  - event_signals_raw_20trading.csv')
print('  - event_signal_counts_20trading.csv')
print('  - event_daily_signal_counts.csv')
print('  - event_per_symbol_bias.csv')
print('  - event_type_distribution.csv')
