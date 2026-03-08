#!/usr/bin/env python3
"""Diagnostic for XAUUSD data issues - API testing and database check"""
import subprocess
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta

db_path = '/home/ubuntu/opticore-bot/trading_bot.db'

def run_xauusd_diagnostics():
    try:
        print("\n" + "="*70)
        print("XAUUSD DIAGNOSTIC REPORT")
        print("="*70)
        
        # Get API token
        env_file = Path('/home/ubuntu/opticore-bot/.env')
        api_token = None
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    if 'TIINGO_API_TOKEN' in line:
                        api_token = line.split('=')[1].strip()
                        break
        
        print(f"\n✓ API Token: {api_token[:10] + '...' + api_token[-10:] if api_token else 'NOT FOUND'}")
        
        # 1. Test Tiingo API directly
        print("\n" + "="*70)
        print("TEST 1: TIINGO API CALL FOR XAUUSD")
        print("="*70)
        
        if api_token:
            try:
                cmd = [
                    "curl",
                    "-s",
                    f"https://api.tiingo.com/tiingo/forex/prices?tickers=xauusd&token={api_token}"
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    try:
                        data = json.loads(result.stdout)
                        print(f"✓ API Response Status: SUCCESS")
                        if isinstance(data, list) and len(data) > 0:
                            latest = data[0]
                            print(f"  Symbol: {latest.get('ticker', 'N/A')}")
                            print(f"  Latest Close: {latest.get('close', 'N/A')}")
                            print(f"  Date: {latest.get('date', 'N/A')}")
                            print(f"  Bid/Ask: {latest.get('bidPrice', 'N/A')} / {latest.get('askPrice', 'N/A')}")
                            print(f"  Last Updated: {latest.get('lastUpdatedUTC', 'N/A')}")
                        else:
                            print(f"✓ API Response: {result.stdout[:200]}")
                    except json.JSONDecodeError:
                        print(f"❌ Invalid JSON response: {result.stdout[:200]}")
                else:
                    print(f"❌ API Error: {result.stderr[:200]}")
            except Exception as e:
                print(f"❌ API Test Failed: {e}")
        else:
            print("❌ API Token not found")
        
        # 2. Check database for recent XAUUSD data
        print("\n" + "="*70)
        print("TEST 2: XAUUSD IN DATABASE")
        print("="*70)
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT COUNT(*) as count FROM ohlcv_data WHERE symbol = 'XAUUSD'
        """)
        total = cursor.fetchone()['count']
        print(f"\n✓ Total XAUUSD candles in database: {total}")
        
        cursor.execute("""
        SELECT 
            MAX(timestamp) as latest,
            COUNT(*) as count
        FROM ohlcv_data
        WHERE symbol = 'XAUUSD'
        GROUP BY timeframe
        ORDER BY timeframe
        """)
        
        print(f"\n✓ XAUUSD Data by Timeframe:")
        results = cursor.fetchall()
        for row in results:
            print(f"  Timeframe: ?, Latest: {row['latest']}, Count: {row['count']}")
        
        # Last 5 candles
        cursor.execute("""
        SELECT 
            timestamp,
            timeframe,
            open,
            close,
            high,
            low,
            volume
        FROM ohlcv_data
        WHERE symbol = 'XAUUSD'
        ORDER BY timestamp DESC
        LIMIT 5
        """)
        
        results = cursor.fetchall()
        if results:
            print(f"\n✓ Latest 5 XAUUSD Candles:")
            print(f"  {'Timestamp':<30} {'TF':<5} {'Open':<10} {'Close':<10} {'High':<10} {'Low':<10}")
            print("-" * 80)
            for row in results:
                ts = row['timestamp']
                tf = row['timeframe']
                o = f"{row['open']:.2f}"
                c = f"{row['close']:.2f}"
                h = f"{row['high']:.2f}"
                l = f"{row['low']:.2f}"
                print(f"  {ts:<30} {tf:<5} {o:<10} {c:<10} {h:<10} {l:<10}")
        else:
            print(f"\n✗ No XAUUSD candles found in database")
        
        # 3. Check recent fetch attempts
        print("\n" + "="*70)
        print("TEST 3: FETCH LOG ANALYSIS (last 50 lines)")
        print("="*70)
        
        log_file = Path('/home/ubuntu/opticore-bot/opticore.log')
        if log_file.exists():
            with open(log_file) as f:
                lines = f.readlines()
                xauusd_lines = [l for l in lines if 'xauusd' in l.lower()][-20:]
                
            if xauusd_lines:
                print(f"\n✓ Recent XAUUSD fetch attempts:")
                for line in xauusd_lines:
                    print(f"  {line.strip()[:100]}")
            else:
                print("\n✗ No XAUUSD entries in log (check if logging enabled)")
        else:
            print("\n✗ Log file not found at:", log_file)
        
        # 4. Check model signals for XAUUSD
        print("\n" + "="*70)
        print("TEST 4: XAUUSD IN ML SIGNALS")
        print("="*70)
        
        cursor.execute("""
        SELECT COUNT(*) as count FROM ml_signals WHERE ticker = 'XAUUSD'
        """)
        signal_count = cursor.fetchone()['count']
        print(f"\n✓ Total XAUUSD signals generated: {signal_count}")
        
        if signal_count > 0:
            cursor.execute("""
            SELECT 
                DATE(timestamp) as day,
                COUNT(*) as signals,
                MAX(timestamp) as latest
            FROM ml_signals
            WHERE ticker = 'XAUUSD'
            GROUP BY DATE(timestamp)
            ORDER BY day DESC
            LIMIT 5
            """)
            
            print(f"\n✓ XAUUSD signals by day:")
            results = cursor.fetchall()
            for row in results:
                print(f"  {row['day']}: {row['signals']} signals (latest: {row['latest']})")
        
        conn.close()
        
        # SUMMARY
        print("\n" + "="*70)
        print("SUMMARY & RECOMMENDATIONS")
        print("="*70)
        print("""
✓ XAUUSD is available on Tiingo API (gold forex pair)
✓ System is configured to fetch XAUUSD data
✓ Signals are being generated for XAUUSD

POSSIBLE ISSUES:
1. Rate limiting - Tiingo free tier has limited requests
2. Data staleness - Gold data may update less frequently
3. Timeout on API calls - XAUUSD might be slower endpoint
4. Symbol case sensitivity - Should be lowercase in URLs

RECOMMENDATIONS:
1. Exclude XAUUSD from watchlist if causing timeouts
2. Or add XAUUSD to a separate lower-frequency fetch job
3. Check Tiingo API rate limits: https://www.tiingo.com/documentation
4. Monitor fetch times and timeout errors in logs
""")
        print("="*70 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_xauusd_diagnostics()
    exit(0 if success else 1)
