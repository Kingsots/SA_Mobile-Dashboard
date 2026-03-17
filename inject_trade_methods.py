#!/usr/bin/env python3
import sqlite3

# Add the methods as separate file content to append before bootstrap_strategy_state
trade_code = """
    def save_trade(self, trade_data):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            direction = 'BUY' if trade_data.get('direction') == 1 else ('SELL' if trade_data.get('direction') == -1 else 'NEUTRAL')
            cursor.execute("INSERT INTO trades (trade_id, symbol, interval, direction, entry_price, stop_loss, take_profit, risk_reward, entry_type, signal_time, expiry_time, strategy, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (trade_data.get('trade_id'), trade_data.get('symbol') or trade_data.get('ticker'), trade_data.get('interval'), direction, trade_data.get('entry_price'), trade_data.get('stop_loss'), trade_data.get('take_profit'), trade_data.get('risk_reward'), trade_data.get('entry_type', 'Breakout Confirmation'), trade_data.get('signal_time') or trade_data.get('timestamp'), trade_data.get('expiry_time') or trade_data.get('expiry_timestamp'), trade_data.get('strategy') or trade_data.get('source'), trade_data.get('status', 'ACTIVE')))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            try:
                conn.close()
            except:
                pass
            return False
        except Exception as e:
            logging.error(f"Error saving trade: {e}")
            try:
                conn.close()
            except:
                pass
            return False

    def trade_exists(self, symbol, interval, direction, entry_price):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            tolerance = abs(entry_price) * 0.0001 if entry_price != 0 else 0.0001
            cursor.execute("SELECT trade_id FROM trades WHERE symbol = ? AND interval = ? AND direction = ? AND ABS(entry_price - ?) < ? AND status = 'ACTIVE' LIMIT 1", (symbol, interval, direction, entry_price, tolerance))
            result = cursor.fetchone()
            conn.close()
            return result is not None
        except Exception as e:
            logging.error(f"Error checking trade existence: {e}")
            try:
                conn.close()
            except:
                pass
            return False

"""

# Read original file
with open('/home/ubuntu/SilentAnalyst/core/database.py', 'r') as f:
    original = f.read()

# Find insertion point
marker = "    def bootstrap_strategy_state(self)"
if marker not in original:
    print("ERROR: Could not find bootstrap_strategy_state")
    exit(1)

# Insert methods before bootstrap_strategy_state
modified = original.replace(marker, trade_code + marker)

# Write back
with open('/home/ubuntu/SilentAnalyst/core/database.py', 'w') as f:
    f.write(modified)

print("✅ Trade methods added successfully")
