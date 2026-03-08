#!/usr/bin/env python3
"""
OptiCore Fail-Safe Heartbeat Watchdog
Monitors last_heartbeat.txt and auto-restarts service if stale >2h
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import requests

# Configuration
HEARTBEAT_THRESHOLD_HOURS = 6  # Increased from 2 to 6 to avoid interrupting model training

# Paths
BASE_DIR = Path("/home/ubuntu/opticore-bot")
HEARTBEAT_FILE = BASE_DIR / "logs" / "last_heartbeat.txt"
LOG_FILE = BASE_DIR / "logs" / "failsafe.log"
SCHEDULER_LOG = BASE_DIR / "scheduler.log"
ENV_FILE = BASE_DIR / ".env"


def _parse_heartbeat_timestamp(timestamp_str):
    """Return naive UTC datetime from heartbeat string."""
    raw = (timestamp_str or "").strip()
    if not raw:
        raise ValueError("empty timestamp")

    iso_candidate = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso_candidate)
        if parsed.tzinfo:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        pass

    fmts = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
    ]

    for fmt in fmts:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue

    raise ValueError(f"unsupported timestamp format: {raw}")


def log(msg):
    """Write to failsafe log with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(log_msg + "\n")
    except Exception as e:
        print(f"⚠️  Log write failed: {e}")

def load_env():
    """Load BOT_TOKEN and CHAT_ID from .env"""
    env_vars = {}
    try:
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    env_vars[key.strip()] = val.strip()
    except Exception as e:
        log(f"❌ Failed to load .env: {e}")
    return env_vars

def send_telegram(token, chat_id, message):
    """Send Telegram alert"""
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            log(f"✅ Telegram alert sent")
            return True
        else:
            log(f"⚠️  Telegram returned {resp.status_code}")
            return False
    except Exception as e:
        log(f"❌ Telegram send failed: {e}")
        return False

def is_training_in_progress():
    """Check if model training is currently in progress"""
    try:
        # Check last 100 lines of scheduler log for training keywords
        result = subprocess.run(
            ["tail", "-n", "100", str(SCHEDULER_LOG)],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            recent_logs = result.stdout.lower()
            training_keywords = ["training model", "train_pipeline", "xgboost training"]
            
            for keyword in training_keywords:
                if keyword in recent_logs:
                    log(f"⏳ Training detected: '{keyword}' found in recent logs")
                    return True
        return False
    except Exception as e:
        log(f"⚠️  Could not check training status: {e}")
        return False

def restart_service():
    """Restart opticore.service via systemctl"""
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "restart", "opticore.service"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            log("✅ opticore.service restarted successfully")
            return True
        else:
            log(f"❌ Service restart failed: {result.stderr}")
            return False
    except Exception as e:
        log(f"❌ Service restart exception: {e}")
        return False

def is_trading_day():
    """Return True if today is Monday-Friday"""
    today = datetime.now(timezone.utc).weekday()
    return today < 5  # 0=Mon, 4=Fri, 5=Sat, 6=Sun

def check_heartbeat():
    """Check heartbeat file and take action if stale"""
    log("🔍 Checking heartbeat...")
    
    # Load env
    env = load_env()
    bot_token = env.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        log("⚠️  Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in .env")
        return
    
    # Check if heartbeat file exists
    if not HEARTBEAT_FILE.exists():
        log(f"⚠️  Heartbeat file missing: {HEARTBEAT_FILE}")
        msg = (
            "⚠️ *OptiCore Watchdog Alert*\n\n"
            f"Heartbeat file not found:\n`{HEARTBEAT_FILE}`\n\n"
            "Service may not be running properly."
        )
        send_telegram(bot_token, chat_id, msg)
        return
    
    # Read last heartbeat timestamp
    try:
        with open(HEARTBEAT_FILE) as f:
            timestamp_str = f.read().strip()

        last_heartbeat = _parse_heartbeat_timestamp(timestamp_str)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        age = now - last_heartbeat
        
        log(f"   Last heartbeat: {timestamp_str}")
        log(f"   Age: {age.total_seconds() / 3600:.1f}h")
        
        # Check if stale (>6 hours)
        if age > timedelta(hours=HEARTBEAT_THRESHOLD_HOURS):
            log("🚨 HEARTBEAT STALE - Checking if safe to restart")
            
            # Only alert and restart during trading week (Mon-Fri)
            is_trading = is_trading_day()
            
            # Check if training is in progress
            if is_training_in_progress():
                log("⏳ Training in progress — skipping restart.")
                if is_trading:
                    msg = (
                        "⏳ *OptiCore Watchdog: Training Detected*\n\n"
                        f"Last heartbeat: `{timestamp_str}`\n"
                        f"Age: `{age.total_seconds() / 3600:.1f}h` (threshold: {HEARTBEAT_THRESHOLD_HOURS}h)\n\n"
                        "Model training in progress.\n"
                        "Skipping restart to avoid interrupting training."
                    )
                    send_telegram(bot_token, chat_id, msg)
                return
            
            # Only restart and alert during trading week
            if not is_trading:
                log(f"⏳ Weekend detected — skipping restart (service will start Sunday night)")
                return
            
            # Send alert
            msg = (
                "🚨 *OptiCore Watchdog: Service Frozen*\n\n"
                f"Last heartbeat: `{timestamp_str}`\n"
                f"Age: `{age.total_seconds() / 3600:.1f}h` (threshold: {HEARTBEAT_THRESHOLD_HOURS}h)\n\n"
                "🔄 Auto-restarting opticore.service..."
            )
            send_telegram(bot_token, chat_id, msg)
            
            # Restart service
            if restart_service():
                success_msg = (
                    "✅ *OptiCore Auto-Recovery*\n\n"
                    "Service restarted successfully.\n"
                    "Monitoring resumed."
                )
                send_telegram(bot_token, chat_id, success_msg)
            else:
                fail_msg = (
                    "❌ *OptiCore Recovery Failed*\n\n"
                    "Service restart command failed.\n"
                    "Manual intervention required."
                )
                send_telegram(bot_token, chat_id, fail_msg)
        else:
            log(f"✅ Heartbeat fresh ({age.total_seconds() / 60:.0f}m old)")
    
    except ValueError as e:
        log(f"❌ Failed to parse timestamp '{timestamp_str}': {e}")
    except Exception as e:
        log(f"❌ Heartbeat check failed: {e}")

if __name__ == "__main__":
    try:
        check_heartbeat()
    except Exception as e:
        log(f"❌ Watchdog crashed: {e}")
        sys.exit(1)
