import sqlite3
from datetime import datetime

conn = sqlite3.connect('trading_bot.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check latest signals
cursor.execute("""
    SELECT * FROM ml_signals 
    ORDER BY timestamp DESC 
    LIMIT 5
""")

print("\n" + "="*140)
print("LATEST SIGNALS IN DATABASE")
print("="*140 + "\n")

rows = cursor.fetchall()
if rows:
    for row in rows:
        timestamp = row['timestamp']
        ticker = row['ticker']
        signal = row['signal']
        interval = row['interval']
        
        # Try to get trade construction fields (may not exist yet)
        try:
            entry_price = row['entry_price'] if 'entry_price' in dict(row).keys() else None
        except:
            entry_price = None
        
        if signal == 1:
            signal_str = '🟢 BUY'
        elif signal == -1:
            signal_str = '🔴 SELL'
        else:
            signal_str = '⚪ NEUTRAL'
        
        print(f"{timestamp} | {ticker:<10} {interval:<6} {signal_str:<10}")
else:
    print("No signals found")

print("\n" + "="*140 + "\n")

conn.close()
