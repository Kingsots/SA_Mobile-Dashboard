import sqlite3

conn = sqlite3.connect('/home/ubuntu/opticore-bot/data/trading_bot.db')
c = conn.cursor()

print("Dropping old api_usage table...")
c.execute("DROP TABLE IF EXISTS api_usage")

print("Creating new api_usage table with correct schema...")
c.execute("""
    CREATE TABLE api_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        api_name TEXT NOT NULL,
        endpoint TEXT,
        ticker TEXT,
        interval TEXT,
        success INTEGER DEFAULT 1,
        error_message TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")

print("Creating indexes...")
c.execute("CREATE INDEX idx_api_usage_timestamp ON api_usage(timestamp)")
c.execute("CREATE INDEX idx_api_usage_api_name ON api_usage(api_name)")

conn.commit()
print("✅ api_usage table recreated with correct schema")

c.execute("PRAGMA table_info(api_usage)")
print("\nNew schema:")
for row in c.fetchall():
    print(f"  {row[1]} ({row[2]})")
