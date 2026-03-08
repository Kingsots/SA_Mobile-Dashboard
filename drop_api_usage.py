import sqlite3
conn = sqlite3.connect('/home/ubuntu/opticore-bot/data/trading_bot.db')
c = conn.cursor()
print("Dropping api_usage table...")
c.execute("DROP TABLE IF EXISTS api_usage")
conn.commit()
print("✅ api_usage table dropped - it will be recreated on next service start")
