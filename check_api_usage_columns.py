import sqlite3
conn = sqlite3.connect('/home/ubuntu/opticore-bot/data/trading_bot.db')
c = conn.cursor()
c.execute("PRAGMA table_info(api_usage)")
print("api_usage columns:")
for row in c.fetchall():
    print(f"  {row[1]} ({row[2]})")
