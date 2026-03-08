import sqlite3

db = sqlite3.connect('trading_bot.db')
c = db.cursor()

# Check volume statistics
c.execute("SELECT symbol, COUNT(*) as total, COUNT(CASE WHEN volume > 0 THEN 1 END) as non_zero FROM ohlcv_data GROUP BY symbol")
print("Volume Statistics:")
print("Symbol | Total | Non-Zero")
for row in c.fetchall():
    print(f"{row[0]:10} | {row[1]:5} | {row[2]:5}")

db.close()
