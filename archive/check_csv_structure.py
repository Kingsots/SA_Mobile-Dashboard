#!/usr/bin/env python3
"""
Check CSV file structure
"""

import pandas as pd
from pathlib import Path

def check_csv_structure():
    # Check all CSV files in the current directory
    csv_files = list(Path('.').glob('*.csv'))
    
    if not csv_files:
        print("❌ No CSV files found in the current directory")
        return
    
    for csv_file in csv_files:
        print(f"\n📊 Checking {csv_file.name}:")
        
        try:
            # Read just the first few rows to check structure
            df = pd.read_csv(csv_file, nrows=5)
            print(f"  Columns: {list(df.columns)}")
            print(f"  First few rows:")
            print(df.head())
            
            # Check if we have datetime information
            possible_date_cols = ['date', 'time', 'timestamp', 'datetime']
            date_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in possible_date_cols)]
            
            if date_cols:
                print(f"  ✅ Found potential date column(s): {date_cols}")
            else:
                print("  ⚠️ No obvious date column found")
                
            # Check if we have OHLC data
            ohlc_cols = []
            for col in df.columns:
                col_lower = col.lower()
                if 'open' in col_lower:
                    ohlc_cols.append(f"Open: {col}")
                elif 'high' in col_lower:
                    ohlc_cols.append(f"High: {col}")
                elif 'low' in col_lower:
                    ohlc_cols.append(f"Low: {col}")
                elif 'close' in col_lower:
                    ohlc_cols.append(f"Close: {col}")
                elif 'volume' in col_lower:
                    ohlc_cols.append(f"Volume: {col}")
            
            if ohlc_cols:
                print(f"  ✅ Found OHLC data: {', '.join(ohlc_cols)}")
            else:
                print("  ⚠️ No obvious OHLC columns found")
                
        except Exception as e:
            print(f"  ❌ Error reading CSV file: {e}")

if __name__ == "__main__":
    check_csv_structure()