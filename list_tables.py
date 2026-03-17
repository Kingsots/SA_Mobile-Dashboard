import sqlite3

conn = sqlite3.connect('trading_bot.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()

print("\nDatabase Tables:")
print("-" * 50)

for table in tables:
    tablename = table[0]
    cursor.execute(f"SELECT COUNT(*) FROM {tablename}")
    count = cursor.fetchone()[0]
    print(f"{tablename:<30} {count:>10} records")

print("-" * 50)
conn.close()
