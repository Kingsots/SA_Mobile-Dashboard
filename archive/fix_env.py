#!/usr/bin/env python3
"""
Fix Environment Variables Loading
"""

import os
from pathlib import Path
from dotenv import load_dotenv

def fix_env_loading():
    """Load environment variables properly"""
    print("🔧 Fixing environment variables loading...")
    
    # Load from .env file
    load_dotenv()
    
    # Check if variables are now available
    print("\nEnvironment variables after loading:")
    for key in ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 'ALPHA_VANTAGE_API_KEY', 'TWELVE_DATA_API_KEY']:
        value = os.getenv(key)
        if value:
            print(f"✅ {key}: {value[:5]}...{value[-5:] if len(value) > 10 else ''}")
        else:
            print(f"❌ {key}: Not set")
    
    # Test Telegram connection
    test_telegram()

def test_telegram():
    """Test Telegram connection"""
    print("\n🤖 Testing Telegram connection...")
    
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("❌ Telegram credentials not available")
        return False
    
    try:
        import requests
        
        url = f"https://api.telegram.org/bot{token}/getMe"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            print("✅ Telegram bot is connected and working!")
            return True
        else:
            print(f"❌ Telegram API error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Telegram connection failed: {e}")
        return False

if __name__ == "__main__":
    fix_env_loading()