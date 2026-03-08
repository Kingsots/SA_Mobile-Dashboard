#!/usr/bin/env python3
"""
CRITICAL DIAGNOSTIC: Check if lag1 features are MISSING for event-driven signals
This would cause predict_signal to return NEUTRAL (0.0) prematurely
"""
import sqlite3
import json
import sys

db_path = '/home/ubuntu/opticore-bot/trading_bot.db'

conn = sqlite3.connect(db_path)
c = conn.cursor()

# Get 100 recent event-driven signals
c.execute("""
    SELECT id, timestamp, ticker, interval, signal, feature_snapshot
    FROM ml_signals 
    WHERE triggered_by LIKE 'event:%' 
    ORDER BY timestamp DESC
    LIMIT 100
""")

signals = c.fetchall()

print("=" * 120)
print("CHECKING: Do event-driven signals have lag1 features?")
print("=" * 120)
print()

lag1_features = [
    'ema_21_lag1', 'ema_100_lag1', 'rsi_14_lag1',
    'volume_sma_20_lag1', 'volume_ratio_lag1',
    'obv_lag1', 'ad_lag1', 'vwap_slope_lag1'
]

missing_lag1_count = 0
has_lag1_count = 0
partial_lag1_count = 0

for sig_id, timestamp, ticker, interval, signal, feature_snapshot in signals:
    try:
        if isinstance(feature_snapshot, str):
            features_dict = json.loads(feature_snapshot)
        else:
            features_dict = feature_snapshot or {}
        
        # Check which lag1 features are present
        found_lag1 = [f for f in lag1_features if f in features_dict]
        missing_lag1 = [f for f in lag1_features if f not in features_dict]
        
        if len(missing_lag1) == len(lag1_features):
            missing_lag1_count += 1
            print(f"❌ Signal {sig_id} ({timestamp}, {ticker} {interval}): ALL lag1 features MISSING!")
            print(f"   DB signal: {signal}")
            print(f"   Available features: {list(features_dict.keys())[:10]}")
            print()
        elif len(missing_lag1) > 0:
            partial_lag1_count += 1
            print(f"⚠️  Signal {sig_id} ({timestamp}, {ticker} {interval}): PARTIAL lag1 features")
            print(f"    Found {len(found_lag1)}/{len(lag1_features)}: {found_lag1}")
            print(f"    Missing: {missing_lag1}")
            print(f"    DB signal: {signal}")
            print()
        else:
            has_lag1_count += 1
    
    except Exception as e:
        print(f"Error on signal {sig_id}: {str(e)}")

print()
print("=" * 120)
print("SUMMARY:")
print(f"  With ALL lag1 features: {has_lag1_count} signals")
print(f"  With PARTIAL lag1 features: {partial_lag1_count} signals")
print(f"  With NO lag1 features: {missing_lag1_count} signals")
print("=" * 120)

if missing_lag1_count > 0:
    print()
    print("🚨 CRITICAL FINDING:")
    print("   Event-driven signals are MISSING all required lag1 features!")
    print("   This means:")
    print("   1. predict_signal() sees missing columns and returns NEUTRAL (0.0)")
    print("   2. Model is NEVER CALLED for event-driven signals")
    print("   3. All event-driven signals default to NEUTRAL")
    print("   4. This explains 0% SELL in database!")
    print()
    print("   ROOT CAUSE: Feature snapshot doesn't include lag1 features")
    print("   SOLUTION: Compute lag1 features from raw OHLC before storing snapshot")

elif partial_lag1_count > 0:
    print()
    print("⚠️  WARNING:")
    print("   Some event-driven signals have incomplete lag1 features")
    print("   This may cause some signals to default to NEUTRAL")

else:
    print()
    print("✅ All event-driven signals have complete lag1 features")
    print("   If signals are still NEUTRAL in DB, bug is elsewhere")

conn.close()
