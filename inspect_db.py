import sqlite3
conn = sqlite3.connect('/home/ubuntu/opticore-bot/data/trading_bot.db')
c = conn.cursor()

print("=== ALL INDEXES ===")
c.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite%'")
for row in c.fetchall():
    print(f"\nIndex: {row[0]}")
    print(f"Table: {row[1]}")
    print(f"SQL: {row[2]}")

print("\n\n=== ALL TABLES ===")
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite%'")
for row in c.fetchall():
    print(f"- {row[0]}")
