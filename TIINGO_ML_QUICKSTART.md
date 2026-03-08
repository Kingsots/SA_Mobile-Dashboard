# Tiingo + ML Pipeline Quick Start Guide

## 🚀 Quick Start - 5 Steps to ML Signals

### **Step 1: Verify Installation**
```bash
# Ensure all dependencies installed
pip install xgboost apscheduler aiohttp joblib scikit-learn

# Run test suite
python test_tiingo_pipeline.py
```

### **Step 2: Fetch Tiingo Data**
```python
import asyncio
from data.tiingo_fetcher import TiingoFetcher

async def fetch():
    async with TiingoFetcher() as fetcher:
        # Fetch 1h data for all watchlist symbols
        results = await fetcher.fetch_batch('1h')
        print(f"Fetched data for {len(results)} symbols")

asyncio.run(fetch())
```

### **Step 3: Generate Features**
```python
from features.engine import FeatureEngine

engine = FeatureEngine()

# Generate features for all symbols (1h timeframe)
results = engine.process_all_tickers('1h')
print(f"Generated features for {len(results)} symbols")
```

### **Step 4: Train Model**
```python
from models.xgb_trainer import XGBTrainer

trainer = XGBTrainer()

# Train XGBoost model on 90 days of 1h data
model = trainer.train_pipeline(interval='1h', days=90)
```

### **Step 5: Generate Signals**
```python
from signals.xgb_signal_engine import XGBSignalEngine

engine = XGBSignalEngine()

# Generate ML signals for all symbols
signals = engine.generate_signals('1h')

# Get actionable signals (BUY/SELL with high confidence)
actionable = engine.get_actionable_signals(signals)

for signal in actionable:
    print(f"{signal['ticker']:10} {signal['signal_label']:8} (conf: {signal['confidence']:.1%})")
```

---

## 📊 Complete Example Script

```python
"""
Complete ML Pipeline Example
Fetch → Feature → Train → Signal
"""

import asyncio
from data.tiingo_fetcher import TiingoFetcher
from features.engine import FeatureEngine
from models.xgb_trainer import XGBTrainer
from signals.xgb_signal_engine import XGBSignalEngine

async def run_ml_pipeline():
    """Run full ML pipeline"""
    
    # 1. Fetch Tiingo data
    print("\n1️⃣  Fetching Tiingo data...")
    async with TiingoFetcher() as fetcher:
        data = await fetcher.fetch_batch('1h')
    print(f"   ✅ Fetched {len(data)} symbols")
    
    # 2. Generate features
    print("\n2️⃣  Generating features...")
    feature_engine = FeatureEngine()
    features = feature_engine.process_all_tickers('1h')
    print(f"   ✅ Features for {len(features)} symbols")
    
    # 3. Train model
    print("\n3️⃣  Training XGBoost model...")
    trainer = XGBTrainer()
    model = trainer.train_pipeline(interval='1h', days=90)
    
    if model:
        print("   ✅ Model trained and deployed")
    else:
        print("   ⚠️  Model trained but not deployed (accuracy < 65%)")
    
    # 4. Generate signals
    print("\n4️⃣  Generating signals...")
    signal_engine = XGBSignalEngine()
    signals = signal_engine.generate_signals('1h')
    
    # 5. Show actionable signals
    actionable = signal_engine.get_actionable_signals(signals)
    
    print(f"\n5️⃣  Actionable Signals: {len(actionable)}")
    for signal in actionable:
        emoji = "🟢" if signal['signal'] == 1 else "🔴"
        print(f"   {emoji} {signal['ticker']:10} {signal['signal_label']:8} (conf: {signal['confidence']:.2%})")

if __name__ == '__main__':
    asyncio.run(run_ml_pipeline())
```

---

## 🔧 Configuration Options

### **Enable ML Pipeline**
```python
# core/config.py
USE_TIINGO_PIPELINE = True  # Turn ON the ML pipeline
```

### **Adjust Model Threshold**
```python
# core/config.py
ML_TARGET_ACCURACY = 0.70  # Require 70% accuracy (default: 0.65)
ML_SIGNAL_CONFIDENCE_MIN = 0.70  # Require 70% confidence (default: 0.60)
```

### **Change XGBoost Parameters**
```python
# core/config.py
XGBOOST_N_ESTIMATORS = 300  # More trees (default: 200)
XGBOOST_MAX_DEPTH = 6  # Deeper trees (default: 4)
XGBOOST_LEARNING_RATE = 0.03  # Slower learning (default: 0.05)
```

---

## 📈 Monitoring

### **Check API Usage**
```python
from data.tiingo_fetcher import TiingoFetcher, RateLimiter
from core.database import DatabaseManager

db = DatabaseManager()
limiter = RateLimiter(db)

stats = limiter.get_usage_stats()
print(f"Hourly: {stats['hourly_used']}/{stats['hourly_limit']}")
print(f"Daily: {stats['daily_used']}/{stats['daily_limit']}")
```

### **View Model Training History**
```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('trading_bot.db')
df = pd.read_sql_query("""
    SELECT timestamp, model_version, accuracy, deployed 
    FROM model_training_log 
    ORDER BY timestamp DESC 
    LIMIT 10
""", conn)
print(df)
conn.close()
```

### **Check Recent ML Signals**
```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('trading_bot.db')
df = pd.read_sql_query("""
    SELECT timestamp, ticker, 
           CASE signal 
               WHEN 1 THEN 'BUY'
               WHEN -1 THEN 'SELL'
               ELSE 'NEUTRAL'
           END as signal,
           confidence 
    FROM ml_signals 
    ORDER BY timestamp DESC 
    LIMIT 20
""", conn)
print(df)
conn.close()
```

---

## 🧹 Maintenance

### **Cleanup Old Data**
```python
from core.database import DatabaseManager

db = DatabaseManager()

# Remove data older than 90 days
db.cleanup_old_data(days=90)
```

### **Retrain Model**
```python
from models.xgb_trainer import XGBTrainer

trainer = XGBTrainer()

# Retrain on fresh data
model = trainer.train_pipeline(interval='1h', days=90)
```

---

## ⚠️ Troubleshooting

### **Problem: No model found**
```
⚠️  No deployed model found at data/models/model_current.pkl
```
**Solution:** Train a model first
```python
from models.xgb_trainer import XGBTrainer
trainer = XGBTrainer()
trainer.train_pipeline(interval='1h', days=90)
```

### **Problem: Rate limit exceeded**
```
❌ Rate limit exceeded: Hourly limit reached: 45/45
```
**Solution:** Wait for rate limit to reset (1 hour) or use CSV fallback
```python
from data.tiingo_fetcher import TiingoFetcher
fetcher = TiingoFetcher()
df = fetcher.fallback_to_csv('EURUSD', '1h')
```

### **Problem: Insufficient training data**
```
❌ Insufficient samples for training: 50
```
**Solution:** Fetch more historical data first (need at least 100 samples)
```python
import asyncio
from data.tiingo_fetcher import TiingoFetcher

async def fetch_historical():
    async with TiingoFetcher() as fetcher:
        # Fetch 90 days of data
        df = await fetcher.fetch_price('EURUSD', '1h', days=90)

asyncio.run(fetch_historical())
```

### **Problem: Model accuracy below threshold**
```
⚠️  Model below deployment threshold (62.5% < 65.0%)
```
**Solution:** This is normal - model is saved but not deployed. Options:
1. Lower threshold: `Config.ML_TARGET_ACCURACY = 0.60`
2. Fetch more data for training
3. Adjust XGBoost parameters
4. Add more features

---

## 🎯 Performance Tips

### **1. Batch Operations**
Always fetch/process multiple symbols at once:
```python
# ✅ GOOD - Batch fetch
results = await fetcher.fetch_batch('1h', symbols=['EURUSD', 'GBPUSD', 'USDJPY'])

# ❌ BAD - Individual fetches
for symbol in symbols:
    df = await fetcher.fetch_price(symbol, '1h')  # Too slow!
```

### **2. Use Database Caching**
Check database before fetching:
```python
# Try database first
df = db.load_raw_ohlcv('EURUSD', '1h', days=7)

# Only fetch if missing
if df is None or df.empty:
    df = await fetcher.fetch_price('EURUSD', '1h')
```

### **3. Scheduled Jobs**
Run expensive operations off-peak:
```python
# Run model training at EOD (23:00 UTC)
# Run feature generation once per hour
# Run signal generation every 30 minutes
```

---

## 📚 API Reference

### **TiingoFetcher**
```python
async with TiingoFetcher() as fetcher:
    # Single fetch
    df = await fetcher.fetch_price(ticker, interval, start_date, end_date)
    
    # Batch fetch
    results = await fetcher.fetch_batch(interval, symbols)
    
    # Rate limit stats
    stats = fetcher.rate_limiter.get_usage_stats()
```

### **FeatureEngine**
```python
engine = FeatureEngine()

# Single ticker
df_features = engine.generate_features_for_ticker(ticker, interval, days)
engine.save_features_to_db(ticker, interval, df_features)

# All tickers
results = engine.process_all_tickers(interval, symbols)
```

### **XGBTrainer**
```python
trainer = XGBTrainer()

# Train model
model = trainer.train_pipeline(ticker, interval, days)

# Load training data
df = trainer.load_training_data(ticker, interval, days)

# Prepare features
X, y = trainer.prepare_features(df)
```

### **XGBSignalEngine**
```python
engine = XGBSignalEngine()

# Generate signals
signals = engine.generate_signals(interval, symbols)

# Single signal
signal_data = engine.generate_signal(ticker, interval)

# Filter actionable
actionable = engine.get_actionable_signals(signals)
```

---

## 🎓 Learn More

- **Implementation Details:** See `TIINGO_ML_IMPLEMENTATION.md`
- **Test Suite:** Run `python test_tiingo_pipeline.py`
- **Code Examples:** Check docstrings in source files
- **Configuration:** Review `core/config.py`

---

## ✅ Checklist

Before enabling `USE_TIINGO_PIPELINE = True`:

- [ ] Dependencies installed (`xgboost`, `apscheduler`, `aiohttp`, etc.)
- [ ] Database migration complete (6 new tables)
- [ ] Tiingo data fetched for at least 90 days
- [ ] Features generated and saved to database
- [ ] Model trained with accuracy ≥ 65%
- [ ] Test suite passes (`python test_tiingo_pipeline.py`)
- [ ] Rate limits understood (50/hour, 1000/day)
- [ ] Monitoring in place (API usage, model performance)

---

**Ready to go? Enable the pipeline:**

```python
# core/config.py
USE_TIINGO_PIPELINE = True
```

Then run your bot as usual - ML signals will automatically supplement OptiCore strategy signals! 🚀
