#!/usr/bin/env python3
"""
Check for existing data files
"""

from pathlib import Path
import pandas as pd

print("📁 Checking for existing data files...")

# Check for CSV files
csv_files = list(Path('.').glob('*.csv'))
print(f"Found {len(csv_files)} CSV files:")
for file in csv_files:
    print(f"  📄 {file.name}")
    
    # Try to read the file
    try:
        df = pd.read_csv(file, nrows=5)
        print(f"    Columns: {list(df.columns)}")
        print(f"    First few rows:")
        print(df.head())
        print()
    except Exception as e:
        print(f"    ❌ Error reading: {e}")
        print()

# Check for database
db_file = Path('trading_bot.db')
if db_file.exists():
    print(f"✅ Database file exists: {db_file}")
else:
    print(f"❌ Database file does not exist: {db_file}")