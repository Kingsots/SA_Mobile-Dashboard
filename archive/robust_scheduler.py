import schedule
import time
import subprocess
import os
import datetime
import logging

# --- Logging Setup ---
logging.basicConfig(
    filename="scheduler.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def run_bot():
    """Run the trading bot in monitor mode"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\nRunning bot at {now}")
    print("=" * 60)
    try:
        result = subprocess.run(
            ["python", "main.py", "monitor"],
            capture_output=True,
            text=True,
            check=False
        )
        print("Bot output:")
        print(result.stdout)
        if result.stderr:
            print("Errors:")
            print(result.stderr)
            logging.error(f"Errors from bot: {result.stderr}")
    except Exception as e:
        print(f"Error running bot: {e}")
        logging.error(f"Error running bot: {e}")

def monday_backfill():
    """Run backfill and retrain every Monday morning"""
    print("\n=== Weekly Monday Refresh (Backfill + Training) ===")
    try:
        result = subprocess.run(["python", "main.py", "backfill"], capture_output=True, text=True, check=False)
        print("Backfill output:")
        print(result.stdout)
        if result.stderr:
            print("Backfill errors:")
            print(result.stderr)
            logging.error(f"Backfill errors: {result.stderr}")
        
        result = subprocess.run(["python", "train_model.py"], capture_output=True, text=True, check=False)
        print("Training output:")
        print(result.stdout)
        if result.stderr:
            print("Training errors:")
            print(result.stderr)
            logging.error(f"Training errors: {result.stderr}")
    except Exception as e:
        print(f"Backfill/Training failed: {e}")
        logging.error(f"Backfill/Training failed: {e}")

if __name__ == "__main__":
    print("Starting robust scheduler...")
    logging.info("Scheduler started.")

    # Monday morning backfill + training at 07:00
    schedule.every().monday.at("07:00").do(monday_backfill)

    # Run bot every hour
    schedule.every().hour.do(run_bot)
    print("Bot will run every hour, backfill every Monday 07:00")
    print("Press Ctrl+C to stop")

    while True:
        try:
            schedule.run_pending()
            time.sleep(10)
        except KeyboardInterrupt:
            print("Scheduler stopped by user")
            logging.info("Scheduler stopped by user")
            break