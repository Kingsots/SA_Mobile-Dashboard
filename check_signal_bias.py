#!/usr/bin/env python3
import sqlite3
from datetime import datetime, timedelta, timezone

DB='trading_bot.db'
conn=sqlite3.connect(DB)
c=conn.cursor()

# Inspect schema
print('SCHEMA ml_signals:')
for r in c.execute("PRAGMA table_info(ml_signals)"):
    print(r)

# Determine columns
cols = [r[1] for r in c.execute("PRAGMA table_info(ml_signals)")]
has_conf = 'confidence' in cols or 'confidence_score' in cols or 'score' in cols
conf_col = 'confidence' if 'confidence' in cols else ('confidence_score' if 'confidence_score' in cols else ('score' if 'score' in cols else None))

now = datetime.now(timezone.utc)
cutoff = (now - timedelta(days=14)).isoformat()
print('\nAnalyzing signals since', cutoff)

# Total counts
q_total = 'SELECT COUNT(*) FROM ml_signals WHERE timestamp >= ?'
q_by_signal = 'SELECT signal, COUNT(*) FROM ml_signals WHERE timestamp >= ? GROUP BY signal'
q_by_day = "SELECT substr(timestamp,1,10) as day, signal, COUNT(*) FROM ml_signals WHERE timestamp >= ? GROUP BY day, signal ORDER BY day DESC"
q_by_symbol = 'SELECT ticker, signal, COUNT(*) FROM ml_signals WHERE timestamp >= ? GROUP BY ticker, signal ORDER BY ticker'

print('\nTotal signals (14d):')
c.execute(q_total,(cutoff,))
print(c.fetchone()[0])

print('\nSignal distribution (14d): signal -> count')
for r in c.execute(q_by_signal,(cutoff,)):
    print(r)

print('\nPer-day signal counts (last 14 days): day | signal | count')
for r in c.execute(q_by_day,(cutoff,)):
    print(r)

print('\nPer-symbol bias (ticker | buy_count | sell_count | neutral_count | total | pct_buy)')
# build per-symbol dict
sym = {}
for ticker, signal, cnt in c.execute(q_by_symbol,(cutoff,)):
    d = sym.setdefault(ticker, {'buy':0,'sell':0,'neutral':0})
    if signal==1:
        d['buy'] = cnt
    elif signal==-1:
        d['sell'] = cnt
    else:
        d['neutral'] = cnt

for t, d in sym.items():
    total = d['buy']+d['sell']+d['neutral']
    pct_buy = (d['buy']/total*100) if total>0 else 0
    print(t, d['buy'], d['sell'], d['neutral'], total, f"{pct_buy:.1f}%")

# Confidence stats if available
if conf_col:
    print(f"\nConfidence stats by signal using column '{conf_col}':")
    q_conf = f"SELECT signal, AVG({conf_col}), COUNT(*) FROM ml_signals WHERE timestamp >= ? GROUP BY signal"
    for r in c.execute(q_conf,(cutoff,)):
        print(r)
else:
    print('\nNo confidence column found; skipping confidence analysis')

conn.close()
