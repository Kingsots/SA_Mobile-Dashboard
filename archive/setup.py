#!/usr/bin/env python3
"""
Quick Setup and Installation Script for Trading Bot
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    print("🚀 Trading Bot Quick Setup")
    print("=" * 40)
    
    # Step 1: Check Python version
    print("1️⃣ Checking Python version...")
    if sys.version_info >= (3, 7):
        print(f"   ✅ Python {sys.version_info.major}.{sys.version_info.minor} - Good!")
    else:
        print(f"   ❌ Python {sys.version_info.major}.{sys.version_info.minor} - Need 3.7+")
        return False
    
    # Step 2: Install packages
    print("2️⃣ Installing required packages...")
    packages = ['requests', 'pandas', 'numpy']
    
    for package in packages:
        try:
            print(f"   Installing {package}...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', package], 
                         check=True, capture_output=True)
            print(f"   ✅ {package} installed")
        except subprocess.CalledProcessError:
            print(f"   ⚠️ {package} might already be installed")
    
    # Step 3: Check .env file
    print("3️⃣ Checking .env file...")
    env_path = Path('.env')
    
    if env_path.exists():
        print("   ✅ .env file exists")
        
        # Check content
        with open(env_path, 'r') as f:
            content = f.read()
        
        if 'TELEGRAM_BOT_TOKEN' in content and 'TELEGRAM_CHAT_ID' in content:
            print("   ✅ Telegram credentials found")
        else:
            print("   ⚠️ .env file missing some credentials")
    else:
        print("   ❌ .env file not found")
        print("   💡 Make sure your .env file contains:")
        print("   TELEGRAM_BOT_TOKEN=your_token_here")
        print("   TELEGRAM_CHAT_ID=your_chat_id_here")
    
    print("\n🎉 Setup complete!")
    print("\nNext steps:")
    print("1. Run: python main.py test")
    print("2. Run: python main.py analyze")  
    print("3. Run: python main.py monitor")
    
    return True

if __name__ == "__main__":
    main()