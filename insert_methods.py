import sys

# Read the file
with open('async_scheduler.py', 'r') as f:
    lines = f.readlines()

# Find the line number where "def register_jobs(self):" appears
target_line = None
for i, line in enumerate(lines):
    if 'def register_jobs(self):' in line:
        target_line = i
        break

if target_line is None:
    print("ERROR: Could not find 'def register_jobs(self):' line")
    sys.exit(1)

print(f"Found register_jobs at line {target_line + 1}")

# The methods to insert with proper indentation (4 spaces for class level)
methods_to_insert = '''    def _crypto_signals_wrapper(self, interval: str):
        """Sync wrapper for async crypto signals - runs in new loop"""
        try:
            import asyncio
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                new_loop.run_until_complete(self.generate_crypto_signals_job(interval))
            finally:
                new_loop.close()
        except Exception as e:
            logger.error(f"Crypto signals wrapper error: {e}", exc_info=True)

    async def generate_crypto_signals_job(self, interval: str):
        """Generate crypto signals for given interval"""
        try:
            logger.info(f"📊 Generating crypto signals for {interval}")
            # Call the main signal generation
            await self.generate_signals_job(interval)
        except Exception as e:
            logger.error(f"Error generating crypto signals for {interval}: {e}", exc_info=True)

    async def _send_crypto_signal_to_private_bot(self, symbol: str, signal_data: dict):
        """Send crypto signal to private bot"""
        try:
            logger.info(f"📤 Sending crypto signal for {symbol}: {signal_data}")
            # Implementation for sending to Telegram private bot
            # This should use the TelegramBot instance
            if hasattr(self, 'telegram_bot') and self.telegram_bot:
                await self.telegram_bot.send_signal(symbol, signal_data)
        except Exception as e:
            logger.error(f"Error sending crypto signal: {e}", exc_info=True)

'''

# Insert the methods before the target line
lines.insert(target_line, methods_to_insert)

# Write the file back
with open('async_scheduler.py', 'w') as f:
    f.writelines(lines)

print("✅ Methods inserted successfully with proper indentation")
