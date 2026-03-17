import sqlite3

conn = sqlite3.connect('trading_bot.db')
cursor = conn.cursor()

# Get table schema
cursor.execute("PRAGMA table_info(ml_signals)")
columns = cursor.fetchall()

print("\nml_signals table columns:")
print("-" * 70)
for col in columns:
    col_id, name, type_, notnull, default, pk = col
    print(f"  {name:<25} {type_:<15} {'NOT NULL' if notnull else 'nullable':<15}")

print("-" * 70)

# Get a sample row
cursor.execute("SELECT * FROM ml_signals LIMIT 1")
row = cursor.fetchone()
if row:
    print("\nSample data (first row):")
    col_names = [description[0] for description in cursor.description]
    for name, value in zip(col_names, row):
        print(f"  {name:<25} = {str(value)[:60]}")

conn.close()
