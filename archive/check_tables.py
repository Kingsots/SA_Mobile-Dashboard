import sqlite3

DB_FILE = "trading_bot.db"

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print("Tables in DB:", cursor.fetchall())
conn.close()
