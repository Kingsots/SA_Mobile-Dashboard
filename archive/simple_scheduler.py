#!/usr/bin/env python3
"""
Simple Scheduler - No External Dependencies
"""

import time
import subprocess
from datetime import datetime

def run_bot():
    """Run the trading bot"""
    print(f"\n⏰ Running bot at {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 50)
    
    # Run the bot
    result = subprocess.run(["python", "ultimate_bot.py"], capture_output=True, text=True)
    
    print("Bot output:")
    print(result.stdout)
    if result.stderr:
        print("Errors:")
        print(result.stderr)

def main():
    """Main scheduling function"""
    print("🕐 Starting scheduler...")
    print("Bot will run every hour")
    
    # Run immediately
    run_bot()
    
    # Calculate seconds until next hour
    now = datetime.now()
    next_hour = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    wait_seconds = (next_hour - now).total_seconds()
    
    print(f"⏰ Next run at: {next_hour.strftime('%H:%M:%S')}")
    time.sleep(wait_seconds)
    
    # Run every hour
    while True:
        run_bot()
        time.sleep(3600)  # Wait 1 hour

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️ Scheduler stopped by user")