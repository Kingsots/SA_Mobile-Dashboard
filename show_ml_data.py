import sqlite3
from datetime import datetime

conn = sqlite3.connect('trading_bot.db')
cursor = conn.cursor()

print("\n" + "="*70)
print("  📊 ML PIPELINE DATA STATUS")
print("="*70)

# Check raw data
print("\n1️⃣  RAW DATA (ohlcv_raw):")
cursor.execute("""
    SELECT ticker, interval, COUNT(*) as rows, 
           MIN(timestamp) as earliest, MAX(timestamp) as latest 
    FROM ohlcv_raw 
    GROUP BY ticker, interval
    ORDER BY ticker, interval
""")
for row in cursor.fetchall():
    print(f"   {row[0]:8s} {row[1]:4s}: {row[2]:5d} rows | {row[3][:10]} to {row[4][:10]}")

# Check features
print("\n2️⃣  FEATURES:")
cursor.execute("SELECT COUNT(*) FROM features")
count = cursor.fetchone()[0]
if count > 0:
    cursor.execute("""
        SELECT ticker, interval, COUNT(*) 
        FROM features 
        GROUP BY ticker, interval
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]:8s} {row[1]:4s}: {row[2]} records")
else:
    print("   ⚠️  No features generated yet")
    print("   💡 Run: features/engine.py to generate")

# Check signals
print("\n3️⃣  ML SIGNALS:")
cursor.execute("SELECT COUNT(*) FROM ml_signals")
count = cursor.fetchone()[0]
if count > 0:
    cursor.execute("""
        SELECT ticker, signal, confidence, timestamp 
        FROM ml_signals 
        ORDER BY timestamp DESC 
        LIMIT 5
    """)
    for row in cursor.fetchall():
        signal_label = "BUY" if row[1] == 1 else "SELL" if row[1] == -1 else "HOLD"
        print(f"   {row[0]:8s} {signal_label:4s} @ {row[2]:.1f}% | {row[3]}")
else:
    print("   ⚠️  No signals generated yet")
    print("   💡 Signals generate at hourly :05 (e.g., 16:05, 17:05)")

# Check rate limits
print("\n4️⃣  API RATE LIMITS:")
cursor.execute("""
    SELECT api_name, period, request_count, period_end 
    FROM rate_limits 
    ORDER BY period, period_end DESC 
    LIMIT 2
""")
rows = cursor.fetchall()
if rows:
    for row in rows:
        end_dt = datetime.fromisoformat(row[3].replace('Z', '+00:00'))
        print(f"   {row[0]:10s} {row[1]:7s}: {row[2]:3d} requests | Resets: {end_dt.strftime('%H:%M:%S')}")
else:
    print("   No rate limit data yet")

# Check model training
print("\n5️⃣  MODEL TRAINING:")
cursor.execute("""
    SELECT model_version, accuracy, train_samples, timestamp 
    FROM model_training_log 
    ORDER BY timestamp DESC 
    LIMIT 1
""")
row = cursor.fetchone()
if row:
    print(f"   Latest: {row[0]} | Accuracy: {row[1]:.1%} | Samples: {row[2]} | {row[3]}")
else:
    print("   ⚠️  No model trained yet")
    print("   💡 Model trains at EOD (23:00 UTC) or run: models/xgb_trainer.py")

print("\n" + "="*70)
print()

conn.close()
