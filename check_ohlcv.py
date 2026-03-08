import sqlite3

db = "/home/ubuntu/SilentAnalyst/trading_bot.db"
conn = sqlite3.connect(db)
cursor = conn.cursor()

# Get schema
cursor.execute("PRAGMA table_info(ohlcv_data)")
print("=== OHLCV_DATA SCHEMA ===")
for row in cursor.fetchall():
    print(f"{row[1]:<20} {row[2]}")

# Get count and sample
cursor.execute("SELECT COUNT(*) FROM ohlcv_data WHERE timestamp > datetime('now', '-5 hours')")
count = cursor.fetchone()[0]
print(f"\n=== FRESH DATA (Last 5 Hours) ===")
print(f"Total candles: {count}")

if count > 0:
    cursor.execute("SELECT * FROM ohlcv_data WHERE timestamp > datetime('now', '-5 hours') LIMIT 1")
    sample = cursor.fetchone()
    cols = [desc[0] for desc in cursor.description]
    print("\nSample row:")
    for col, val in zip(cols, sample):
        print(f"  {col}: {val}")

conn.close()
