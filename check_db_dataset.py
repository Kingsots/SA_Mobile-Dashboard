import sqlite3

conn = sqlite3.connect('trading_bot.db')
cursor = conn.cursor()

print("\n" + "="*70)
print("  📊 DATABASE TABLES & DATASETS")
print("="*70)

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()

for table in tables:
    table_name = table[0]
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    
    print(f"\n{table_name}:")
    print(f"  Rows: {count:,}")
    
    # Show sample data for each table
    if count > 0:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"  Columns: {', '.join(columns[:5])}{'...' if len(columns) > 5 else ''}")
        
        # Show date range for tables with timestamp
        if 'timestamp' in columns:
            cursor.execute(f"SELECT MIN(timestamp), MAX(timestamp) FROM {table_name}")
            min_date, max_date = cursor.fetchone()
            if min_date and max_date:
                print(f"  Date range: {min_date[:10]} to {max_date[:10]}")

print("\n" + "="*70)
print()

conn.close()
