import sqlite3
import pandas as pd
import os

# Path to your SQLite DB
DB_PATH = "1trading_bot.db"   # adjust if your DB file has a different name
EXPORT_DIR = "exports"       # folder where CSVs will be saved

def export_all_tables():
    # Create export folder if not exists
    if not os.path.exists(EXPORT_DIR):
        os.makedirs(EXPORT_DIR)

    # Connect to DB
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    if not tables:
        print("⚠️ No tables found in the database.")
        return

    print(f"Found {len(tables)} tables: {[t[0] for t in tables]}")

    # Export each table to CSV
    for table_name, in tables:
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        file_path = os.path.join(EXPORT_DIR, f"{table_name}.csv")
        df.to_csv(file_path, index=False)
        print(f"✅ Exported {table_name} → {file_path}")

    conn.close()
    print("\n🎉 All tables exported successfully!")

if __name__ == "__main__":
    export_all_tables()
