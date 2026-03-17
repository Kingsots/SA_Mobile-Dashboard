#!/usr/bin/env python3
"""
Fix pipeline by replacing broadcast call with proper save-first flow.
"""

with open('/home/ubuntu/SilentAnalyst/signals/xgb_signal_engine_ec2.py', 'r') as f:
    lines = f.readlines()

# Find the broadcast line
for i, line in enumerate(lines):
    if 'self.broadcast_trade_signal(signal_data)' in line and i > 300:
        # Found it - now we need to replace section before it
        # Look backwards for the BROADCAST comment
        j = i - 1
        while j >= 0 and 'BROADCAST TO TELEGRAM' not in lines[j]:
            j -= 1
        
        if j >= 0:
            # Found start of broadcast section
            # Replace from comment to after return
            # Get all lines from BROADCAST comment to return
            k = i + 1
            while k < len(lines) and 'return signal_data' not in lines[k]:
                k += 1
            
            if k < len(lines):
                # Now replace lines[j:k+1] with new code
                new_code = [
                    "        # STEP 5: CHECK FOR DUPLICATE (prevent broadcast spam)\n",
                    "        dir_text = 'BUY' if trade_signal.direction == 1 else 'SELL'\n",
                    "        if self.db.trade_exists(ticker, interval, dir_text, trade_signal.entry_price):\n",
                    "            logging.info(f'Trade already exists: {ticker}-{interval} {dir_text}')\n",
                    "            return None\n",
                    "\n",
                    "        # STEP 6: SAVE TO DATABASE (persist trade first)\n",
                    "        saved = self.db.save_trade(signal_data)\n",
                    "        if not saved:\n",
                    "            logging.warning(f'Failed to save trade {ticker}-{interval}')\n",
                    "            return None\n",
                    "\n",
                    "        # STEP 7: BROADCAST TO TELEGRAM (only after persistence)\n",
                    "        self.broadcast_trade_signal(signal_data)\n",
                    "\n",
                    "        return signal_data\n"
                ]
                
                # Remove old lines and insert new ones
                del lines[j:k+1]
                for idx, new_line in enumerate(new_code):
                    lines.insert(j + idx, new_line)
                
                print(f"✅ Pipeline fixed at line {j}")
                break

# Write back
with open('/home/ubuntu/SilentAnalyst/signals/xgb_signal_engine_ec2.py', 'w') as f:
    f.writelines(lines)

print("✅ Execute pipeline corrected")
