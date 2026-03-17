#!/usr/bin/env python3
"""
Fix the execute_trade_pipeline to save to DB before broadcasting.
Prevents duplicate broadcasts via trade_exists check.
"""

with open('/home/ubuntu/SilentAnalyst/signals/xgb_signal_engine_ec2.py', 'r') as f:
    content = f.read()

# Old broken flow
old_flow = """        # ══════════════════════════════════════════════════════════════════════════
        # BROADCAST TO TELEGRAM
        # ══════════════════════════════════════════════════════════════════════════

        self.broadcast_trade_signal(signal_data)

        return signal_data"""

# New corrected flow
new_flow = """        # ══════════════════════════════════════════════════════════════════════════
        # STEP 5: CHECK FOR DUPLICATE (prevent broadcast spam)
        # ══════════════════════════════════════════════════════════════════════════

        dir_text = 'BUY' if trade_signal.direction == 1 else 'SELL'
        if self.db.trade_exists(ticker, interval, dir_text, trade_signal.entry_price):
            logging.info(f"[{source}] Trade already exists: {ticker}-{interval} {dir_text} @ {trade_signal.entry_price}")
            return None

        # ══════════════════════════════════════════════════════════════════════════
        # STEP 6: SAVE TO DATABASE (persist trade first)
        # ══════════════════════════════════════════════════════════════════════════

        saved = self.db.save_trade(signal_data)
        if not saved:
            logging.warning(f"[{source}] Failed to save trade {ticker}-{interval} to database")
            return None

        # ══════════════════════════════════════════════════════════════════════════
        # STEP 7: BROADCAST TO TELEGRAM (only after successful persistence)
        # ══════════════════════════════════════════════════════════════════════════

        self.broadcast_trade_signal(signal_data)

        return signal_data"""

# Replace
if old_flow in content:
    content = content.replace(old_flow, new_flow)
    print("✅ Pipeline flow updated (save before broadcast)")
else:
    print("❌ Could not find old flow pattern")
    exit(1)

# Also need to initialize db in __init__
# Check if db is initialized
if 'self.db = None' not in content and 'self.db =' not in content:
    # Find __init__ and add db initialization
    init_marker = "def __init__(self):"
    if init_marker in content:
        # Find where to add (look for first assignment in __init__)
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'def __init__(self):' in line:
                # Find next indented line
                for j in range(i+1, min(i+20, len(lines))):
                    if lines[j].strip() and not lines[j].startswith(' '*8):
                        # Found first real line
                        if 'from core.database import DatabaseManager' not in content:
                            # Add import at top if needed
                            pass
                        # Insert db initialization
                        lines.insert(j, '        self.db = DatabaseManager()')
                        content = '\n'.join(lines)
                        print("✅ DatabaseManager initialized in __init__")
                        break
                break

# Write back
with open('/home/ubuntu/SilentAnalyst/signals/xgb_signal_engine_ec2.py', 'w') as f:
    f.write(content)

print("✅ Execute pipeline corrected: save → broadcast")
