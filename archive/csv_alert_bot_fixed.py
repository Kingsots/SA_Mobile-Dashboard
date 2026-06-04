#!/usr/bin/env python3
"""
Simple Alert Scheduler
"""

import time
import schedule
from datetime import datetime

def run_alerts():
    """Run the alert bot"""
    print(f"\n⏰ Running alerts at {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 50)
    
    # Run the CSV alert bot
    import subprocess
    result = subprocess.run(["python", "csv_alert_bot_fixed.py"], capture_output=True, text=True)
    
    print("Alert bot output:")
    print(result.stdout)
    if result.stderr:
        print("Errors:")
        print(result.stderr)

def main():
    """Main scheduling function"""
    print("🕐 Starting alert scheduler...")
    print("Alerts will run every hour at :00")
    
    # Schedule to run every hour
    schedule.every().hour.at(":00").do(run_alerts)
    
    # Also run immediately
    run_alerts()
    
    # Keep the script running
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️ Scheduler stopped by user")