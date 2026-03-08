#!/usr/bin/env python3
"""
Check environment variables
"""

import os
from pathlib import Path

def check_env():
    env_path = Path('.env')
    if env_path.exists():
        print("✅ .env file exists")
        with open(env_path, 'r') as f:
            content = f.read()
            print("Contents of .env file:")
            print(content)
    else:
        print("❌ No .env file found")
    
    print("\nEnvironment variables:")
    for key in ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 'ALPHA_VANTAGE_API_KEY', 'TWELVE_DATA_API_KEY']:
        value = os.getenv(key)
        if value:
            print(f"✅ {key}: {value[:5]}...{value[-5:] if len(value) > 10 else ''}")
        else:
            print(f"❌ {key}: Not set")

if __name__ == "__main__":
    check_env()