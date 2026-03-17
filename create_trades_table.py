#!/usr/bin/env python3
import sqlite3

db_path = '/home/ubuntu/SilentAnalyst/trading_bot.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create trades table
cursor.execute('''CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT UNIQUE,
    symbol TEXT,
    interval TEXT,
    direction TEXT,
    entry_price REAL,
    stop_loss REAL,
    take_profit REAL,
    risk_reward REAL,
    entry_type TEXT,
    signal_time TEXT,
    expiry_time TEXT,
    strategy TEXT,
    status TEXT DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

# Create indexes
cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_symbol_status ON trades(symbol, interval, status)')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_trade_id ON trades(trade_id)')

conn.commit()
conn.close()

print("✅ Trades table created successfully")
