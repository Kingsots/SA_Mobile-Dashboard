#!/usr/bin/env python3
"""
Trading System Monitor
"""

import os
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

def monitor_system():
    """Monitor the trading system status"""
    print("🖥️  Trading System Monitor")
    print("=" * 40)
    
    # Check database
    db_path = "trading_bot.db"
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check ohlcv_data table
        cursor.execute("SELECT COUNT(*) FROM ohlcv_data")
        ohlcv_count = cursor.fetchone()[0]
        
        # Check signals table
        cursor.execute("SELECT COUNT(*) FROM signals")
        signals_count = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"📊 Database: {db_path}")
        print(f"   OHLCV records: {ohlcv_count}")
        print(f"   Signal records: {signals_count}")
    else:
        print("❌ Database not found")
    
    # Check environment variables
    print("\n🔑 Environment Variables:")
    for key in ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']:
        value = os.getenv(key)
        if value:
            print(f"   ✅ {key}: Set")
        else:
            print(f"   ❌ {key}: Not set")
    
    # Check CSV files
    print("\n📁 CSV Files:")
    csv_files = ["US30_1H_MASTER.csv", "XAUUSD_1h.csv", "USDJPY_1h.csv", 
                 "GBPUSD_1h.csv", "EURJPY_1h.csv", "AUDCAD_1h.csv"]
    
    for file in csv_files:
        if os.path.exists(file):
            # Get file size and modification time
            size = os.path.getsize(file)
            mtime = os.path.getmtime(file)
            mtime_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
            print(f"   ✅ {file}: {size} bytes, modified {mtime_str}")
        else:
            print(f"   ❌ {file}: Missing")
    
    # Check Python packages
    print("\n🐍 Python Packages:")
    try:
        import yfinance
        print("   ✅ yfinance: Installed")
    except ImportError:
        print("   ❌ yfinance: Not installed")
    
    try:
        import requests
        print("   ✅ requests: Installed")
    except ImportError:
        print("   ❌ requests: Not installed")
    
    try:
        from dotenv import load_dotenv
        print("   ✅ python-dotenv: Installed")
    except ImportError:
        print("   ❌ python-dotenv: Not installed")

if __name__ == "__main__":
    monitor_system()