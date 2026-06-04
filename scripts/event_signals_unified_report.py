#!/usr/bin/env python3
"""
Unified Event-Driven Signals Bias Report
- Single consolidated file with all data, summaries, and analysis
- Generates both CSV and TXT formats
"""
import argparse
import sqlite3
from datetime import datetime, timedelta, timezone
import csv
import os

parser = argparse.ArgumentParser(description='Unified event-driven signal bias report')
parser.add_argument('--db', default='trading_bot.db', help='Path to trading_bot.db')
parser.add_argument('--days', type=int, default=20, help='Lookback window in trading days')
parser.add_argument('--outdir', default='reports/event_signals_unified', help='Output folder')
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
    print(f'❌ No event-driven signals found in the last {args.days} trading days.')
    conn.close()
    raise SystemExit(1)

print(f'✅ Found {len(rows)} event-driven signals since {cutoff_iso}')

# ==== COMPUTE STATISTICS ====
signal_counts = {}
ticker_signal_counts = {}
daily_counts = {}
event_type_counts = {}
ticker_event_counts = {}

signal_map = {1: 'buy', -1: 'sell', 0: 'neutral'}

for row in rows:
    _, timestamp, ticker, _, signal, confidence, _, event_type = row
    signal_label = signal_map.get(signal, 'unknown')
    day = timestamp.split('T')[0]
    
    signal_counts[signal_label] = signal_counts.get(signal_label, 0) + 1
    
    if ticker not in ticker_signal_counts:
        ticker_signal_counts[ticker] = {'buy': 0, 'sell': 0, 'neutral': 0, 'total': 0, 'confidence_sum': 0}
    ticker_signal_counts[ticker][signal_label] += 1
    ticker_signal_counts[ticker]['total'] += 1
    ticker_signal_counts[ticker]['confidence_sum'] += confidence
    
    if day not in daily_counts:
        daily_counts[day] = {'buy': 0, 'sell': 0, 'neutral': 0, 'total': 0}
    daily_counts[day][signal_label] += 1
    daily_counts[day]['total'] += 1
    
    event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
    
    if ticker not in ticker_event_counts:
        ticker_event_counts[ticker] = {}
    ticker_event_counts[ticker][event_type] = ticker_event_counts[ticker].get(event_type, 0) + 1

# ==== WRITE UNIFIED CSV FILE ====
unified_file = os.path.join(args.outdir, 'event_signals_unified_report.csv')

with open(unified_file, 'w', newline='') as f:
    w = csv.writer(f)
    
    # SECTION 1: METADATA
    w.writerow(['METADATA'])
    w.writerow(['Report Type', 'Event-Driven Signals Analysis (20 Trading Days)'])
    w.writerow(['Generated', datetime.now(timezone.utc).isoformat()])
    w.writerow(['Database', args.db])
    w.writerow(['Lookback Days', args.days])
    w.writerow(['Analysis Period', f'{cutoff_iso} to now'])
    w.writerow(['Total Signals', len(rows)])
    w.writerow([])
    
    # SECTION 2: OVERALL SUMMARY
    w.writerow(['OVERALL SUMMARY'])
    w.writerow(['Total Signals', len(rows)])
    for signal_label in ['buy', 'sell', 'neutral']:
        count = signal_counts.get(signal_label, 0)
        pct = (count / len(rows) * 100) if len(rows) > 0 else 0
        w.writerow([f'{signal_label.upper()} Signals', count, f'{pct:.1f}%'])
    w.writerow(['Unique Tickers', len(ticker_signal_counts)])
    w.writerow(['Unique Event Types', len(event_type_counts)])
    w.writerow([])
    
    # SECTION 3: EVENT TYPE DISTRIBUTION
    w.writerow(['EVENT TYPE DISTRIBUTION'])
    w.writerow(['Event Type', 'Count', 'Percentage'])
    for event_type in sorted(event_type_counts.keys(), key=lambda x: event_type_counts[x], reverse=True):
        count = event_type_counts[event_type]
        pct = (count / len(rows) * 100)
        w.writerow([event_type, count, f'{pct:.1f}%'])
    w.writerow([])
    
    # SECTION 4: TICKER STATISTICS
    w.writerow(['TICKER ANALYSIS'])
    w.writerow(['Ticker', 'Buy Count', 'Sell Count', 'Neutral Count', 'Total', '%Buy', 'Avg Confidence'])
    for ticker in sorted(ticker_signal_counts.keys(), key=lambda x: ticker_signal_counts[x]['total'], reverse=True):
        stats = ticker_signal_counts[ticker]
        total = stats['total']
        pct_buy = (stats['buy'] / total * 100) if total > 0 else 0
        avg_conf = stats['confidence_sum'] / total if total > 0 else 0
        w.writerow([
            ticker,
            stats['buy'],
            stats['sell'],
            stats['neutral'],
            total,
            f'{pct_buy:.1f}%',
            f'{avg_conf:.4f}'
        ])
    w.writerow([])
    
    # SECTION 5: DAILY BREAKDOWN
    w.writerow(['DAILY SIGNAL COUNTS'])
    w.writerow(['Date', 'Buy', 'Sell', 'Neutral', 'Total'])
    for day in sorted(daily_counts.keys(), reverse=True):
        counts = daily_counts[day]
        w.writerow([
            day,
            counts['buy'],
            counts['sell'],
            counts['neutral'],
            counts['total']
        ])
    w.writerow([])
    
    # SECTION 6: RAW SIGNALS
    w.writerow(['RAW SIGNALS (Most Recent First)'])
    w.writerow(['ID', 'Timestamp', 'Ticker', 'Interval', 'Signal', 'Confidence', 'Model Version', 'Event Type'])
    for row in rows:
        signal_label = signal_map.get(row[4], 'unknown')
        w.writerow([row[0], row[1], row[2], row[3], signal_label, f'{row[5]:.4f}', row[6], row[7]])

print(f'✅ Unified report saved: {unified_file}')

# ==== WRITE SUMMARY TEXT FILE ====
summary_file = os.path.join(args.outdir, 'event_signals_summary.txt')

with open(summary_file, 'w') as f:
    f.write('=' * 80 + '\n')
    f.write('EVENT-DRIVEN SIGNALS ANALYSIS REPORT\n')
    f.write(f'Generated: {datetime.now(timezone.utc).isoformat()}\n')
    f.write(f'Analysis Period: {cutoff_iso} to now ({args.days} trading days)\n')
    f.write('=' * 80 + '\n\n')
    
    f.write('OVERALL SUMMARY\n')
    f.write('-' * 80 + '\n')
    f.write(f'Total Event-Driven Signals: {len(rows)}\n')
    for signal_label in ['buy', 'sell', 'neutral']:
        count = signal_counts.get(signal_label, 0)
        pct = (count / len(rows) * 100) if len(rows) > 0 else 0
        f.write(f'  {signal_label.upper()}: {count} ({pct:.1f}%)\n')
    f.write(f'Unique Tickers: {len(ticker_signal_counts)}\n')
    f.write(f'Unique Event Types: {len(event_type_counts)}\n\n')
    
    f.write('EVENT TYPE DISTRIBUTION\n')
    f.write('-' * 80 + '\n')
    for event_type in sorted(event_type_counts.keys(), key=lambda x: event_type_counts[x], reverse=True):
        count = event_type_counts[event_type]
        pct = (count / len(rows) * 100)
        f.write(f'  {event_type}: {count} ({pct:.1f}%)\n')
    f.write('\n')
    
    f.write('TOP 15 TICKERS BY TOTAL SIGNALS\n')
    f.write('-' * 80 + '\n')
    f.write(f'{"Ticker":<12} {"Buy":>6} {"Sell":>6} {"Neutral":>8} {"Total":>6} {"%Buy":>7} {"Avg Conf":>10}\n')
    f.write('-' * 80 + '\n')
    for ticker in sorted(ticker_signal_counts.keys(), key=lambda x: ticker_signal_counts[x]['total'], reverse=True)[:15]:
        stats = ticker_signal_counts[ticker]
        total = stats['total']
        pct_buy = (stats['buy'] / total * 100) if total > 0 else 0
        avg_conf = stats['confidence_sum'] / total if total > 0 else 0
        f.write(f'{ticker:<12} {stats["buy"]:>6} {stats["sell"]:>6} {stats["neutral"]:>8} {total:>6} {pct_buy:>6.1f}% {avg_conf:>10.4f}\n')
    f.write('\n')
    
    f.write('RECENT 20 SIGNALS\n')
    f.write('-' * 80 + '\n')
    f.write(f'{"Timestamp":<30} {"Ticker":<10} {"Signal":<8} {"Conf":>8} {"Event Type":<35}\n')
    f.write('-' * 80 + '\n')
    for row in rows[:20]:
        signal_label = signal_map.get(row[4], 'unknown').upper()
        f.write(f'{row[1]:<30} {row[2]:<10} {signal_label:<8} {row[5]:>8.4f} {row[7]:<35}\n')
    f.write('\n')

print(f'✅ Summary text saved: {summary_file}')

conn.close()

print(f'\n📊 Report Files Created in {args.outdir}:')
print(f'  1. event_signals_unified_report.csv - Full data with 6 sections (metadata, summary, stats, daily, raw)')
print(f'  2. event_signals_summary.txt - Human-readable summary with key statistics')
print(f'\n✅ All data unified in ONE file!')
