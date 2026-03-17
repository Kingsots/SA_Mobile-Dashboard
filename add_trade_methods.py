#!/usr/bin/env python3
"""
Add trade persistence methods to DatabaseManager
"""

import sys

# Read the database.py file
db_file = '/home/ubuntu/SilentAnalyst/core/database.py'

with open(db_file, 'r') as f:
    content = f.read()

# Code to insert before bootstrap_strategy_state
trade_methods = '''
    def save_trade(self, trade_data: Dict) -> bool:
        """
        Save a completed trade signal to the unified trades table.
        
        Args:
            trade_data: Dictionary with trade information:
                - trade_id: Unique trade identifier
                - symbol: Trading symbol
                - interval: Timeframe
                - direction: 'BUY' or 'SELL'
                - entry_price, stop_loss, take_profit, risk_reward
                - entry_type: 'Breakout Confirmation' or other
                - signal_time: ISO timestamp when signal created
                - expiry_time: ISO timestamp when signal expires
                - strategy: Strategy name (e.g., 'v2_persistence')
                - status: Signal status ('ACTIVE', 'EXPIRED', 'CANCELLED')
        
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                '''INSERT INTO trades 
                (trade_id, symbol, interval, direction, entry_price, stop_loss, 
                 take_profit, risk_reward, entry_type, signal_time, expiry_time, 
                 strategy, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    trade_data.get('trade_id'),
                    trade_data.get('symbol') or trade_data.get('ticker'),
                    trade_data.get('interval'),
                    'BUY' if trade_data.get('direction') == 1 else 'SELL' if trade_data.get('direction') == -1 else 'NEUTRAL',
                    trade_data.get('entry_price'),
                    trade_data.get('stop_loss'),
                    trade_data.get('take_profit'),
                    trade_data.get('risk_reward'),
                    trade_data.get('entry_type', 'Breakout Confirmation'),
                    trade_data.get('signal_time') or trade_data.get('timestamp'),
                    trade_data.get('expiry_time') or trade_data.get('expiry_timestamp'),
                    trade_data.get('strategy') or trade_data.get('source'),
                    trade_data.get('status', 'ACTIVE')
                )
            )
            
            conn.commit()
            conn.close()
            
            logging.debug(f"✅ Trade saved: {trade_data.get('symbol')}-{trade_data.get('interval')} ID={trade_data.get('trade_id')}")
            return True
            
        except sqlite3.IntegrityError:
            # Duplicate trade_id is OK (ignore)
            logging.debug(f"ℹ️ Trade already exists: {trade_data.get('trade_id')}")
            conn.close()
            return False
            
        except Exception as e:
            logging.error(f"❌ Error saving trade: {e}", exc_info=True)
            try:
                conn.close()
            except:
                pass
            return False

    def trade_exists(self, symbol: str, interval: str, direction: str, entry_price: float) -> bool:
        """
        Check if an identical trade already exists in the database.
        
        Prevents duplicate signals from being broadcast across scheduler sweeps.
        
        Args:
            symbol: Trading symbol
            interval: Timeframe (e.g., '4h', '1h', '30m')
            direction: Trade direction ('BUY', 'SELL')
            entry_price: Entry price (checked with small tolerance)
        
        Returns:
            True if trade exists with status='ACTIVE', False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Query with price tolerance (0.01% difference acceptable)
            tolerance = entry_price * 0.0001
            
            cursor.execute(
                '''SELECT trade_id FROM trades
                WHERE symbol = ?
                AND interval = ?
                AND direction = ?
                AND ABS(entry_price - ?) < ?
                AND status = 'ACTIVE'
                LIMIT 1
                ''',
                (symbol, interval, direction, entry_price, tolerance)
            )
            
            result = cursor.fetchone()
            conn.close()
            
            exists = result is not None
            if exists:
                logging.debug(f"ℹ️ Trade exists: {symbol}-{interval} {direction} @ {entry_price}")
            
            return exists
            
        except Exception as e:
            logging.error(f"❌ Error checking trade existence: {e}")
            try:
                conn.close()
            except:
                pass
            return False

'''

# Find the line number where bootstrap_strategy_state starts
lines = content.split('\n')
insert_line = None
for i, line in enumerate(lines):
    if 'def bootstrap_strategy_state' in line:
        insert_line = i
        break

if insert_line is None:
    print("❌ Could not find bootstrap_strategy_state method")
    sys.exit(1)

# Insert the trade methods before bootstrap_strategy_state
lines.insert(insert_line, trade_methods)

# Write back to file
modified_content = '\n'.join(lines)
with open(db_file, 'w') as f:
    f.write(modified_content)

print("✅ Trade methods added to DatabaseManager")
