#!/usr/bin/env python3
"""
Test Telegram integration
"""

import os
import requests
from pathlib import Path

def load_env():
    """Load environment variables from .env file"""
    env_path = Path('.env')
    if env_path.exists():
        print(f"✅ Loading .env file from: {env_path.absolute()}")
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
                    print(f"  📝 Set {key.strip()}")
    else:
        print(f"⚠️ No .env file found at: {env_path.absolute()}")

load_env()

# Telegram credentials
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def test_telegram():
    """Test Telegram integration"""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ Telegram credentials not found in environment")
        return False
    
    print(f"Testing Telegram with token: {TELEGRAM_TOKEN[:10]}... and chat ID: {CHAT_ID}")
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': CHAT_ID,
            'text': '🤖 AI Trading Bot Test Message\n✅ Telegram integration working!',
            'parse_mode': 'Markdown'
        }
        
        response = requests.post(url, data=payload, timeout=10)
        
        if response.status_code == 200:
            print("✅ Telegram test successful! Message sent.")
            return True
        else:
            print(f"❌ Telegram API error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Telegram error: {e}")
        return False

if __name__ == "__main__":
    test_telegram()