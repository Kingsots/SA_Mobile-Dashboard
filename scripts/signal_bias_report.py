"""
Signal-bias deep-dive report generator
- Connects to a local or EC2 `trading_bot.db`
- Computes 14-day signal distribution, per-symbol stats, daily counts
- Outputs CSVs and PNG charts for a full report

Usage (local):
    python scripts/signal_bias_report.py --db trading_bot.db
Usage (EC2):
    python3 scripts/signal_bias_report.py --db /home/ubuntu/opticore-bot/data/trading_bot.db --outdir /home/ubuntu/opticore-bot/reports/signal_bias

Outputs:
 - <outdir>/signal_counts_14d.csv
 - <outdir>/per_symbol_bias.csv
 - <outdir>/daily_signal_counts.png
 - <outdir>/per_symbol_bias_top20.png
 - <outdir>/confidence_distribution.png
 - <outdir>/rolling_bias_7d.png
"""
import argparse
import sqlite3
from datetime import datetime, timedelta, timezone
import pandas as pd
import matplotlib.pyplot as plt
import os

try:
    plt.style.use('seaborn-darkgrid')
except Exception:
    try:
        plt.style.use('ggplot')
    except Exception:
        pass

parser = argparse.ArgumentParser(description='Signal bias deep-dive report')
parser.add_argument('--db', default='trading_bot.db', help='Path to trading_bot.db')
parser.add_argument('--days', type=int, default=14, help='Lookback window in days')
parser.add_argument('--outdir', default='reports/signal_bias', help='Output folder for CSVs and charts')
args = parser.parse_args()

os.makedirs(args.outdir, exist_ok=True)

cutoff = (datetime.now(timezone.utc) - timedelta(days=args.days)).isoformat()

conn = sqlite3.connect(args.db)

# load table
q = f"SELECT * FROM ml_signals WHERE timestamp >= '{cutoff}'"
df = pd.read_sql_query(q, conn, parse_dates=['timestamp'])
conn.close()

if df.empty:
    print('No signals found in the last', args.days, 'days. Exiting.')
    raise SystemExit(0)

# normalize signal labels
signal_map = {1: 'buy', -1: 'sell', 0: 'neutral'}
df['signal_label'] = df['signal'].map(signal_map)

df.to_csv(os.path.join(args.outdir, 'signals_raw_14d.csv'), index=False)

# aggregate counts
counts = df['signal_label'].value_counts().rename_axis('signal').reset_index(name='count')
counts.to_csv(os.path.join(args.outdir, 'signal_counts_14d.csv'), index=False)

# per-day counts
df['day'] = df['timestamp'].dt.floor('D')
daily = df.groupby(['day','signal_label']).size().unstack(fill_value=0)
daily.to_csv(os.path.join(args.outdir, 'daily_signal_counts.csv'))

# per-symbol bias
per_sym = df.groupby(['ticker','signal_label']).size().unstack(fill_value=0)
per_sym['total'] = per_sym.sum(axis=1)
per_sym['pct_buy'] = (per_sym.get('buy',0) / per_sym['total']) * 100
per_sym = per_sym.sort_values('pct_buy', ascending=False)
per_sym.to_csv(os.path.join(args.outdir, 'per_symbol_bias.csv'))

# confidence distribution (if present)
conf_col = None
for c in df.columns:
    if c in ('confidence','confidence_score','score'):
        conf_col = c
        break

# Charts
# 1) daily stacked bar
ax = daily.plot(kind='bar', stacked=True, figsize=(10,5), colormap='Accent')
ax.set_title(f'Daily signal counts (last {args.days} days)')
ax.set_xlabel('day')
ax.set_ylabel('count')
plt.tight_layout()
plt.savefig(os.path.join(args.outdir, 'daily_signal_counts.png'))
plt.close()

# 2) top-20 per-symbol bias bar
top20 = per_sym.head(20)
fig, ax = plt.subplots(figsize=(10,6))
ax.barh(top20.index.astype(str), top20['pct_buy'], color='tab:blue')
ax.set_xlabel('% BUY')
ax.set_title('Top 20 tickers by %BUY (14d)')
plt.gca().invert_yaxis()
plt.tight_layout()
plt.savefig(os.path.join(args.outdir, 'per_symbol_bias_top20.png'))
plt.close()

# 3) confidence histograms
if conf_col:
    import numpy as np
    fig, ax = plt.subplots(figsize=(8,4))
    for s, g in df.groupby('signal_label'):
        ax.hist(g[conf_col].dropna(), bins=20, alpha=0.6, label=s)
    ax.set_title('Confidence distribution by signal (14d)')
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(args.outdir, 'confidence_distribution.png'))
    plt.close()

# 4) rolling bias (7-day) for top tickers
rolling = df.copy()
rolling = rolling.sort_values('timestamp')
rolling['date'] = rolling['timestamp'].dt.date

pivot = pd.crosstab(rolling['date'], rolling['ticker'], values=rolling['signal'], aggfunc='sum', dropna=False).fillna(0)
# compute rolling proportion of buys per ticker (7-day window)
buy_mask = (df['signal']==1)
rolling_buy = df[df['signal']==1].groupby(['day','ticker']).size().unstack(fill_value=0)
rolling_total = df.groupby(['day','ticker']).size().unstack(fill_value=0)
rolling_pct_buy = (rolling_buy.rolling(7).sum() / rolling_total.rolling(7).sum()).fillna(0)

# plot top 6 tickers by total signals
top6 = per_sym.head(6).index.tolist()
fig, ax = plt.subplots(figsize=(10,5))
for t in top6:
    series = rolling_pct_buy[t] if t in rolling_pct_buy else None
    if series is not None:
        ax.plot(series.index, series.values, label=t)
ax.set_ylim(0,1)
ax.set_ylabel('7-day pct buy')
ax.set_title('7-day rolling %BUY for top tickers')
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(args.outdir, 'rolling_bias_7d.png'))
plt.close()

print('Report generated in', args.outdir)
print('- CSVs: signal_counts_14d.csv, per_symbol_bias.csv, daily_signal_counts.csv')
print('- Charts: daily_signal_counts.png, per_symbol_bias_top20.png, rolling_bias_7d.png')
if conf_col:
    print('- Confidence chart: confidence_distribution.png')
