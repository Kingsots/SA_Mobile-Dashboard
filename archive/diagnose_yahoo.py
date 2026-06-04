#!/usr/bin/env python3
"""
Diagnose Yahoo Finance issues
"""

import yfinance as yf
import requests
import time

print("🔍 Diagnosing Yahoo Finance connection...")

# Test 1: Check if we can make basic requests
print("\n1. Testing basic internet connection...")
try:
    response = requests.get("https://www.google.com", timeout=10)
    print("✅ Internet connection working")
except Exception as e:
    print(f"❌ Internet connection failed: {e}")
    exit()

# Test 2: Check Yahoo Finance directly
print("\n2. Testing Yahoo Finance API...")
try:
    response = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/AAPL", timeout=10)
    print(f"✅ Yahoo Finance API responding (status: {response.status_code})")
except Exception as e:
    print(f"❌ Yahoo Finance API failed: {e}")

# Test 3: Try different symbols
print("\n3. Testing different symbols...")
test_symbols = ["AAPL", "MSFT", "BTC-USD", "EURUSD=X"]

for symbol in test_symbols:
    try:
        print(f"   Testing {symbol}...")
        ticker = yf.Ticker(symbol)
        info = ticker.info
        print(f"   ✅ {symbol}: {info.get('shortName', 'No name')}")
        time.sleep(1)
    except Exception as e:
        print(f"   ❌ {symbol} failed: {e}")

# Test 4: Try our specific symbols with error handling
print("\n4. Testing our target symbols...")
our_symbols = ["^DJI", "GC=F", "JPY=X"]

for symbol in our_symbols:
    try:
        print(f"   Testing {symbol}...")
        ticker = yf.Ticker(symbol)
        
        # Try to get some basic info first
        try:
            info = ticker.info
            print(f"   ✅ {symbol}: Basic info available")
        except:
            print(f"   ⚠️ {symbol}: No basic info, trying history...")
        
        # Try to get historical data
        hist = ticker.history(period="7d", interval="1h")
        if hist is not None and not hist.empty:
            print(f"   ✅ {symbol}: Got {len(hist)} periods of historical data")
        else:
            print(f"   ❌ {symbol}: No historical data available")
            
        time.sleep(2)
    except Exception as e:
        print(f"   ❌ {symbol} failed with error: {e}")

print("\n🔍 Diagnosis complete!")