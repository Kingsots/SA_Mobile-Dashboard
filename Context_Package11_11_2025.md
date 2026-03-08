# OptiCore Trading Bot - Comprehensive Context Package
**Date**: November 11, 2025  
**Branch**: `deploy/event-driven-system`  
**Last Stable Commit**: 7282fa8 (HIGH-CONFIDENCE FIX: Sanitize timestamp fields)

---

## 🎯 PROJECT OVERVIEW

### Core Mission
Event-driven ML trading bot using XGBoost for signal generation across 15 forex/index symbols, deployed on AWS EC2 with Telegram alerting.

### Architecture Pattern
```
Tiingo API (market data)
    ↓
APScheduler (orchestration)
    ↓
Data Pipeline → Feature Engineering → XGBoost Inference
    ↓
Event Detection (parallel scan) → Signal Generation
    ↓
Telegram Alerts
```

### Technology Stack
- **Language**: Python 3.12
- **ML Framework**: XGBoost 3.1.1, scikit-learn 1.7.2
- **Database**: SQLite3 (9 tables)
- **Scheduler**: APScheduler 3.11.1 (AsyncIOScheduler)
- **Data Source**: Tiingo API (forex/crypto OHLCV)
- **Alerting**: python-telegram-bot 22.5
- **Deployment**: AWS EC2 Ubuntu 24.04.3, systemd service

---

## 📁 CRITICAL FILE STRUCTURE

### Core Application Files
```
async_scheduler.py              # Main orchestrator (613 lines)
├── MLPipelineScheduler class
├── 5 scheduled jobs (fetch_1h, generate_signals, event_monitor, eod_pipeline, health_check)
└── Job execution tracking and error handling

core/
├── database.py                 # DatabaseManager (865 lines)
│   ├── init_database() - Bootstrap 9 tables
│   ├── _run_migrations() - Execute migration registry
│   ├── load_ohlcv_data() - Load last N candles
│   └── save_ml_signal() - Write signals with triggered_by field
├── config.py                   # Config class (380 lines)
│   ├── EVENT_MODE_ENABLED = True (line 300)
│   ├── DB_PATH = "trading_bot.db" (line 151)
│   ├── USE_TIINGO_PIPELINE = True
│   └── SYMBOL_LIST = [15 forex pairs + indices]
└── indicators.py               # Technical indicators (EMA, RSI, OBV, AD, VWAP)

data/
├── tiingo_fetcher.py          # TiingoFetcher with rate limiting
│   ├── Rate limits: 500/hour, 20/minute
│   ├── Retry logic: exponential backoff
│   └── Usage tracking in api_usage table
├── generator.py               # Feature generation from OHLCV
└── csv_loader.py              # Legacy CSV data loader

signals/
├── xgb_signal_engine.py       # XGBSignalEngine (365 lines) ⚠️ CRITICAL
│   ├── generate_signal() - Main inference (lines 253-365)
│   ├── Timestamp sanitization (lines 306-330) - FIXED Nov 10
│   └── Event support via triggered_by parameter
├── event_monitor.py           # EventMonitor orchestration
├── event_filter.py            # MarketEvent dataclass + filtering
├── market_structure.py        # Breakout detection (higher-high, lower-low)
├── volume_volatility.py       # Volume spike + volatility expansion
└── momentum_confirmation.py   # EMA crossover + momentum shift

migrations/
├── 001_tiingo_ml_tables.py    # Create 6 Tiingo/ML tables
│   ├── ohlcv_raw, features, ml_signals
│   ├── api_usage, model_training_log, rate_limits
│   └── Includes triggered_by column
└── 002_add_triggered_by.py    # Idempotent triggered_by column add

alerts/
├── telegram_bot.py            # TelegramBot with async send
└── formatter.py               # Signal formatting for messages
```

---

## 🗄️ DATABASE SCHEMA

### 9 Tables Architecture

#### Legacy Tables (3)
1. **ohlcv_data**
   - Columns: id, symbol, timeframe, timestamp, open, high, low, close, volume, source, created_at
   - Indexes: idx_symbol_timeframe, idx_timestamp
   - Purpose: Original OHLCV storage (pre-Tiingo)

2. **signals**
   - Columns: id, symbol, timeframe, signal_type, confidence, price, indicators, cascade_data, timestamp, created_at
   - Purpose: Legacy signal storage

3. **performance_metrics**
   - Columns: id, total_signals, win_signals, loss_signals, efficiency, profit_factor, avg_trade, max_drawdown, timestamp, created_at
   - Purpose: Backtesting metrics

#### Tiingo/ML Tables (6)
4. **ohlcv_raw**
   - Columns: id, timestamp, ticker, interval, open, high, low, close, volume, source, created_at
   - Indexes: idx_ohlcv_raw_ticker_interval, idx_ohlcv_raw_timestamp
   - UNIQUE constraint: (ticker, interval, timestamp)
   - Purpose: Raw Tiingo data storage

5. **features**
   - Columns: id, timestamp, ticker, interval, open, high, low, close, volume, ema_21, ema_100, rsi_14, obv, ad, vwap, vwap_slope, volume_sma_20, volume_ratio, created_at
   - Indexes: idx_features_ticker_interval, idx_features_timestamp
   - UNIQUE constraint: (ticker, interval, timestamp)
   - Purpose: Engineered features for ML

6. **ml_signals** ⚠️ PRIMARY SIGNAL TABLE
   - Columns: id, timestamp, ticker, interval, signal, confidence, feature_snapshot, model_version, **triggered_by**, created_at
   - Indexes: idx_ml_signals_ticker, idx_ml_signals_timestamp
   - triggered_by: TEXT DEFAULT 'time' (values: 'time', 'event:volume_spike', 'event:breakout', etc.)
   - Purpose: All ML-generated signals (time-based + event-driven)

7. **api_usage**
   - Columns: id, timestamp, api_name, endpoint, ticker, interval, success, error_message, created_at
   - Indexes: idx_api_usage_timestamp, idx_api_usage_api_name
   - Purpose: Tiingo API call tracking

8. **model_training_log**
   - Columns: id, timestamp, model_version, train_samples, test_samples, accuracy, precision_score, recall, f1_score, training_time_seconds, deployed, notes, created_at
   - Indexes: idx_model_log_timestamp
   - Purpose: Model training audit trail

9. **rate_limits**
   - Columns: id, api_name, period, request_count, period_start, period_end, created_at
   - Purpose: Rate limit enforcement tracking

---

## ⚙️ SCHEDULER CONFIGURATION

### 5 Active Jobs

#### Job 1: fetch_1h (Data Ingestion)
```python
Trigger: IntervalTrigger(minutes=60)
Function: fetch_tiingo_data('1h')
Purpose: Fetch 1-hour OHLCV data from Tiingo API
Symbols: 15 (forex pairs + indices)
API Calls: 24/day per symbol (360 total/day)
Next Run: Every hour (e.g., 12:29:04 UTC)
```

#### Job 2: generate_signals (Time-Based ML)
```python
Trigger: CronTrigger(minute=5, hour='*')
Function: generate_signals_job('1h')
Purpose: Generate ML signals using XGBoost model
Frequency: Hourly at :05 (e.g., 11:05, 12:05, 13:05)
Triggered By: 'time'
Expected Output: 0-15 signals per run
```

#### Job 3: event_monitor (Event-Driven Scan)
```python
Trigger: IntervalTrigger(minutes=5)
Function: event_monitor_job('1h')
Purpose: Scan existing DB data for market events
Frequency: Every 5 minutes
Triggered By: 'event:volume_spike', 'event:breakout', etc.
Cooldown: 60 minutes per symbol (prevent duplicate triggers)
Expected Output: 0-N signals per run (event-dependent)
```

#### Job 4: eod_pipeline (Feature Engineering + Training)
```python
Trigger: CronTrigger(hour=23, minute=0, timezone='UTC')
Function: eod_pipeline_job()
Purpose: Daily feature generation and model retraining
Frequency: Once per day at 23:00 UTC
Steps:
  1. Generate features for all symbols
  2. Train XGBoost model on new data
  3. Evaluate and optionally deploy new model
```

#### Job 5: health_check (System Diagnostics)
```python
Trigger: CronTrigger(hour='0,12', minute=0, timezone='UTC')
Function: health_check_job()
Purpose: Comprehensive system health report with Telegram notification
Frequency: Twice daily at 00:00 UTC and 12:00 UTC (fixed times)
Includes: DB size, model status, API rate limits, 24h signal counts, job schedule
Alert: Sends detailed Telegram report every 12 hours
```

**Telegram Health Report Includes:**
- 📊 Database Status (size, total records)
- 🤖 Model Status (active/missing)
- 📡 API Rate Limits (hourly/daily remaining)
- 📈 Signals Last 24h (total, time-based, event-driven)
- ⏰ All Scheduled Jobs (with next run times)
- ✅ System Operational Status

### Removed Jobs
- ❌ **fetch_30m** (removed Nov 10, 2025) - Redundant with event_monitor scanning every 5 min

### Recent Changes (Nov 11, 2025)
- ✅ **health_check interval changed**: 4 hours → 12 hours at fixed times (00:00 & 12:00 UTC)
- ✅ **Telegram health reports added**: Comprehensive system status sent twice daily
- ✅ **New database method**: `get_signal_counts_24h()` for tracking signal generation

---

## 🔧 DEPLOYMENT CONFIGURATION

### EC2 Instance
- **Instance ID**: i-089df0da5be6ffe93
- **OS**: Ubuntu 24.04.3 LTS
- **IP**: 52.90.60.32
- **SSH Key**: C:\Users\bigso\Downloads\opticore-key.pem
- **Repo Path**: ~/opticore-bot
- **Branch**: deploy/event-driven-system

### Systemd Service
```ini
[Unit]
Description=OptiCore ML Trading Bot

[Service]
Type=simple
ExecStart=/home/ubuntu/opticore-bot/.venv/bin/python /home/ubuntu/opticore-bot/async_scheduler.py
WorkingDirectory=/home/ubuntu/opticore-bot
Restart=on-failure
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

**Service Commands**:
```bash
sudo systemctl restart opticore.service
systemctl status opticore.service --no-pager
journalctl -u opticore.service -n 100 --no-pager
journalctl -u opticore.service -f  # Live tail
```

### Python Environment
- **Python**: 3.12.x
- **Virtual Env**: ~/opticore-bot/.venv
- **Pip**: 25.3
- **Packages**: 86 installed

**Critical Dependencies**:
```
pandas==2.3.3
numpy==2.3.4
xgboost==3.1.1
scikit-learn==1.7.2
apscheduler==3.11.1
aiohttp==3.13.2
python-telegram-bot==22.5
yfinance==0.2.66
joblib==1.5.2
requests==2.32.5
python-dotenv==1.2.1
```

### Environment Variables (.env)
```bash
TIINGO_API_KEY=<redacted>
TELEGRAM_BOT_TOKEN=<redacted>
TELEGRAM_CHAT_ID=<redacted>
```

---

## 🐛 KNOWN ISSUES & TROUBLESHOOTING

### ⚠️ CRITICAL ISSUE: Signals Not Being Generated

#### Symptoms
```
Nov 10 11:05:00 - signal_debug - WARNING - EURUSD | NO DATA
Nov 10 11:05:00 - signal_debug - WARNING - GBPUSD | NO DATA
Nov 10 11:05:00 - signal_debug - INFO - SUMMARY: 0 signals generated
```

#### Root Causes (Investigated)
1. **Empty Database After Rollback** (Nov 10, 2025)
   - git clean -fd during emergency rollback deleted data/trading_bot.db
   - Fresh database created with 0 records in all tables
   - Migration 001 verified: 0 ohlcv_raw, 0 features, 0 ml_signals
   - **Status**: Database exists but empty

2. **fetch_1h Job Not Populating Data**
   - Job runs every 60 minutes (confirmed in logs)
   - Need to verify: Is Tiingo API actually being called?
   - Need to verify: Are records being written to ohlcv_raw table?
   - **Check**: `SELECT COUNT(*) FROM ohlcv_raw;` should be > 0 after first fetch

3. **XGBSignalEngine.generate_signal() Failing Silently**
   - Lines 262-264: `df = self.db.load_ohlcv_data(symbol, interval, limit=100)`
   - If df is empty → Line 267 logs "NO DATA" and returns None
   - **Fix Needed**: Add detailed logging in fetch_tiingo_data() to see API response

4. **Tiingo API Issues**
   - Rate limiting: 500 calls/hour across all symbols
   - Authentication failure (check TIINGO_API_KEY)
   - Symbol mapping mismatch (e.g., EURUSD vs eurusd vs EUR/USD)
   - **Test**: Run manual Tiingo API call to verify connectivity

#### Debugging Steps
```bash
# 1. Check database state
ssh -i opticore-key.pem ubuntu@52.90.60.32
cd ~/opticore-bot
.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('data/trading_bot.db')
c = conn.cursor()
print('ohlcv_raw:', c.execute('SELECT COUNT(*) FROM ohlcv_raw').fetchone()[0])
print('features:', c.execute('SELECT COUNT(*) FROM features').fetchone()[0])
print('ml_signals:', c.execute('SELECT COUNT(*) FROM ml_signals').fetchone()[0])
print('api_usage:', c.execute('SELECT COUNT(*) FROM api_usage').fetchone()[0])
"

# 2. Watch live logs for fetch_1h execution
journalctl -u opticore.service -f | grep -E 'fetch_1h|Tiingo|ohlcv_raw'

# 3. Check Tiingo API connectivity
.venv/bin/python -c "
import asyncio
from data.tiingo_fetcher import TiingoFetcher
async def test():
    async with TiingoFetcher() as fetcher:
        data = await fetcher.fetch_ohlcv('EURUSD', '1hour', limit=5)
        print('Data fetched:', len(data) if data else 0)
asyncio.run(test())
"

# 4. Force manual data fetch
.venv/bin/python -c "
import asyncio
from async_scheduler import MLPipelineScheduler
scheduler = MLPipelineScheduler(enable_telegram=False)
asyncio.run(scheduler.fetch_tiingo_data('1h'))
"
```

#### Expected Fix Path
1. Verify Tiingo API connectivity and response format
2. Add detailed logging in TiingoFetcher.fetch_ohlcv()
3. Confirm ohlcv_raw table population after fetch_1h job
4. Ensure DatabaseManager.load_ohlcv_data() returns valid DataFrame
5. Validate XGBoost model can handle empty feature sets gracefully

---

### Other Known Issues

#### 1. Multiple Database Migrations Running
**Symptom**: Migration 001 runs 4-5 times on startup  
**Cause**: Multiple imports of DatabaseManager trigger _run_migrations()  
**Impact**: Minor (migrations are idempotent with CREATE TABLE IF NOT EXISTS)  
**Status**: Low priority

#### 2. Timestamp Field Sanitization
**Fixed**: Nov 10, 2025 (lines 313-317 in xgb_signal_engine.py)  
**Issue**: pd.Timestamp objects in feature_snapshot caused "ValueError: could not convert string to float"  
**Solution**: Dict comprehension filters datetime types before model inference
```python
clean_snapshot = {
    k: (float(v) if pd.notna(v) and not isinstance(v, (pd.Timestamp, datetime)) else None)
    for k, v in features_snapshot.items()
    if not isinstance(v, (pd.Timestamp, datetime))
}
```

#### 3. EC2 venv Corruption Risk
**Symptom**: ModuleNotFoundError after git operations  
**Cause**: git clean -fd can delete .venv/ directory  
**Fix**: Rebuild venv with `python3 -m venv --clear .venv && pip install -r requirements.txt`  
**Prevention**: Add .venv/ to .gitignore (already done)

#### 4. PowerShell SSH Command Quoting Hell
**Issue**: Complex Python one-liners fail due to quote escaping  
**Workaround**: Create temp script file, scp to EC2, execute, delete  
**Example**:
```powershell
# Bad (fails)
ssh ubuntu@host "python -c 'import sys; print(\"test\")'"

# Good (works)
echo "import sys; print('test')" > test.py
scp test.py ubuntu@host:/tmp/test.py
ssh ubuntu@host "python /tmp/test.py"
```

#### 5. datetime.utcnow() Deprecation Warning
**Location**: async_scheduler.py line 249  
**Warning**: `datetime.datetime.utcnow() is deprecated`  
**Fix**: Replace with `datetime.now(datetime.UTC)`  
**Priority**: Low (cosmetic)

---

## 🔑 CRITICAL CODE SECTIONS

### 1. Signal Generation Entry Point
**File**: `signals/xgb_signal_engine.py`  
**Function**: `generate_signal(symbol, interval, triggered_by='time')`  
**Lines**: 253-365

**Critical Flow**:
```python
# Line 262-267: Load OHLCV data
df = self.db.load_ohlcv_data(symbol, interval, limit=100)
if df is None or df.empty:
    signal_logger.warning(f"{symbol:10s} | NO DATA")
    return None

# Line 274-288: Generate features
features_snapshot = self._prepare_features(df)

# Line 306-309: Detect timestamp fields (ADDED Nov 10)
if any(isinstance(v, (pd.Timestamp, datetime)) for v in features_snapshot.values()):
    signal_logger.warning(f"Timestamp fields detected: {[k for k, v in features_snapshot.items() if isinstance(v, (pd.Timestamp, datetime))]}")

# Line 313-317: Sanitize timestamps (ADDED Nov 10)
clean_snapshot = {
    k: (float(v) if pd.notna(v) and not isinstance(v, (pd.Timestamp, datetime)) else None)
    for k, v in features_snapshot.items()
    if not isinstance(v, (pd.Timestamp, datetime))
}

# Line 320-328: XGBoost inference
X_input = pd.DataFrame([clean_snapshot])
prediction = self.model.predict(X_input)[0]
proba = self.model.predict_proba(X_input)[0]

# Line 330-365: Save signal to database
signal_data = {
    'timestamp': latest_timestamp,
    'ticker': symbol,
    'interval': interval,
    'signal': int(prediction),
    'confidence': float(proba[int(prediction)]),
    'features': clean_snapshot,  # Uses sanitized dict
    'model_version': self.model_version,
    'triggered_by': triggered_by
}
self.db.save_ml_signal(signal_data)
```

---

### 2. Data Fetch Job
**File**: `async_scheduler.py`  
**Function**: `fetch_tiingo_data(interval)`  
**Lines**: 116-179

**Critical Flow**:
```python
# Line 127-134: Initialize fetcher
async with TiingoFetcher() as fetcher:
    symbols = Config.get_symbol_list()
    
    # Line 141-173: Fetch each symbol
    for symbol in symbols:
        try:
            ohlcv_data = await fetcher.fetch_ohlcv(
                symbol=symbol,
                interval=interval,
                limit=250
            )
            
            # Line 156-165: Save to database
            if ohlcv_data:
                for candle in ohlcv_data:
                    self.db.save_tiingo_ohlcv(
                        ticker=symbol,
                        interval=interval,
                        timestamp=candle['timestamp'],
                        open=candle['open'],
                        high=candle['high'],
                        low=candle['low'],
                        close=candle['close'],
                        volume=candle['volume']
                    )
```

**⚠️ DEBUG NEEDED**: Add logging after line 156 to confirm data is being saved.

---

### 3. Event Monitor Scan
**File**: `async_scheduler.py`  
**Function**: `event_monitor_job(interval)`  
**Lines**: 219-310

**Critical Flow**:
```python
# Line 249: Cooldown check
now = datetime.utcnow()
self._prune_symbol_cooldowns(now)

# Line 260-266: Load data and scan for events
for symbol in symbols:
    df = self.db.load_ohlcv_data(symbol, interval, limit=250)
    if df is None or df.empty:
        continue
    
    events = self.event_monitor.analyze(symbol, interval, df)
    
    # Line 271-310: Process detected events
    for event in events:
        # Cooldown check
        if symbol in self.symbol_cooldowns:
            continue
        
        # Generate signal via event-driven path
        signal = self.signal_engine.generate_signal(
            symbol=symbol,
            interval=interval,
            triggered_by=f"event:{event.event_type}"
        )
        
        if signal:
            self.symbol_cooldowns[symbol] = now
            triggered += 1
```

**Note**: Event monitor does NOT fetch new data—it only scans existing DB records.

---

### 4. Database Load Function
**File**: `core/database.py`  
**Function**: `load_ohlcv_data(ticker, interval, limit=100)`  
**Lines**: ~450-500 (approximate)

**Critical Query**:
```python
query = """
    SELECT timestamp, open, high, low, close, volume
    FROM ohlcv_raw
    WHERE ticker = ? AND interval = ?
    ORDER BY timestamp DESC
    LIMIT ?
"""
cursor.execute(query, (ticker, interval, limit))
rows = cursor.fetchall()

if not rows:
    return None  # ⚠️ This causes "NO DATA" in signal generation
```

---

## 📊 CURRENT RUNTIME STATE

### Service Status (as of Nov 10, 11:29 UTC)
```
● opticore.service - OptiCore ML Trading Bot
  Active: active (running) since Mon 2025-11-10 11:29:02 UTC
  Main PID: 108556
  Memory: 129.6M (peak: 129.9M)
  CPU: 1.678s
```

### Registered Jobs
```
✅ fetch_1h          - Next: 12:29:04 UTC (interval: 1h)
✅ generate_signals  - Next: 12:05:00 UTC (cron: hourly at :05)
✅ event_monitor     - Next: 11:34:04 UTC (interval: 5min)
✅ eod_pipeline      - Next: 23:00:00 UTC (cron: daily)
✅ health_check      - Next: 15:29:04 UTC (interval: 4h)
```

### Model Status
```
Model Version: 20251110_091532
Accuracy: 100.00% (⚠️ suspiciously high - possible overfitting)
Location: models/xgboost_model_20251110_091532.pkl
Features: 7 (after timestamp sanitization)
```

### Database State
```
Table              | Records
-------------------|--------
ohlcv_raw          | 0       ⚠️ EMPTY
features           | 0       ⚠️ EMPTY
ml_signals         | 0       ⚠️ EMPTY
api_usage          | 0       ⚠️ EMPTY
model_training_log | 0       ⚠️ EMPTY
rate_limits        | 0
ohlcv_data         | Unknown (legacy)
signals            | Unknown (legacy)
performance_metrics| Unknown (legacy)
```

### Recent Log Entries
```
Nov 10 11:05:00 - generate_signals job executed
Nov 10 11:05:00 - SUMMARY: 0 signals generated (all symbols: NO DATA)
Nov 10 11:09:18 - event_monitor sweep complete - no new triggers
Nov 10 11:14:18 - event_monitor sweep complete - no new triggers
Nov 10 11:19:18 - event_monitor sweep complete - no new triggers
Nov 10 11:24:18 - event_monitor sweep complete - no new triggers
```

---

## 🚀 DEPLOYMENT WORKFLOW

### Standard Deployment Process

#### 1. Local Development
```bash
# Make changes
code async_scheduler.py  # or other files

# Test locally (if applicable)
python async_scheduler.py

# Check git status
git status -sb

# Stage changes
git add <files>

# Commit with descriptive message
git commit -m "feat: remove redundant 30m fetch job"
```

#### 2. Deploy to EC2
```bash
# Upload changed files
scp -i C:\Users\bigso\Downloads\opticore-key.pem <files> ubuntu@52.90.60.32:~/opticore-bot/

# If deploying to subdirectory (e.g., core/)
scp -i C:\Users\bigso\Downloads\opticore-key.pem core/database.py ubuntu@52.90.60.32:~/opticore-bot/core/

# Restart service
ssh -i C:\Users\bigso\Downloads\opticore-key.pem ubuntu@52.90.60.32 "sudo systemctl restart opticore.service"

# Wait 5 seconds for startup
Start-Sleep -Seconds 5

# Verify service status
ssh -i C:\Users\bigso\Downloads\opticore-key.pem ubuntu@52.90.60.32 "systemctl status opticore.service --no-pager"
```

#### 3. Monitor Logs
```bash
# View last 100 lines
ssh -i C:\Users\bigso\Downloads\opticore-key.pem ubuntu@52.90.60.32 "journalctl -u opticore.service -n 100 --no-pager"

# Live tail
ssh -i C:\Users\bigso\Downloads\opticore-key.pem ubuntu@52.90.60.32 "journalctl -u opticore.service -f"

# Filter for errors
ssh -i C:\Users\bigso\Downloads\opticore-key.pem ubuntu@52.90.60.32 "journalctl -u opticore.service -n 200 --no-pager | grep -i error"

# Check job registration
ssh -i C:\Users\bigso\Downloads\opticore-key.pem ubuntu@52.90.60.32 "journalctl -u opticore.service --since '5 minutes ago' --no-pager | grep 'Job registered'"
```

#### 4. Rollback (if needed)
```bash
# SSH to EC2
ssh -i C:\Users\bigso\Downloads\opticore-key.pem ubuntu@52.90.60.32

# Navigate to repo
cd ~/opticore-bot

# Check current commit
git log --oneline -5

# Rollback to previous commit
git reset --hard <commit-sha>

# Restart service
sudo systemctl restart opticore.service
```

### Emergency Recovery Procedure

If service fails to start or database is corrupted:

#### Option 1: Restore Database Backup
```bash
ssh -i C:\Users\bigso\Downloads\opticore-key.pem ubuntu@52.90.60.32
cd ~/opticore-bot/data
ls -la trading_bot.db*  # Find backups
cp trading_bot.db.backup trading_bot.db
cd ..
sudo systemctl restart opticore.service
```

#### Option 2: Rebuild Virtual Environment
```bash
ssh -i C:\Users\bigso\Downloads\opticore-key.pem ubuntu@52.90.60.32
cd ~/opticore-bot

# Clear Python cache
find . -name '*.pyc' -delete
find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null

# Rebuild venv
python3 -m venv --clear .venv
.venv/bin/pip install --upgrade pip setuptools wheel
.venv/bin/pip install -r requirements.txt

# Restart service
sudo systemctl restart opticore.service
```

#### Option 3: Nuclear Reset (Last Resort)
```bash
ssh -i C:\Users\bigso\Downloads\opticore-key.pem ubuntu@52.90.60.32
cd ~/opticore-bot

# Backup current state
tar -czf ~/backup_$(date +%Y%m%d_%H%M%S).tar.gz data/ models/ .env

# Reset to clean state
git reset --hard HEAD
git clean -fd  # ⚠️ WARNING: Deletes untracked files

# Rebuild everything
python3 -m venv --clear .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# Restart service
sudo systemctl restart opticore.service
```

---

## 📝 DEVELOPMENT GUIDELINES

### Code Style
- Follow PEP 8 naming conventions
- Use type hints where applicable
- Add docstrings for all functions/classes
- Log at appropriate levels (DEBUG, INFO, WARNING, ERROR)

### Logging Standards
```python
# Use dedicated loggers
signal_logger = logging.getLogger('signal_debug')
event_logger = logging.getLogger('event_debug')

# Log levels
logger.debug("Detailed diagnostic info")
logger.info("Normal operation info")
logger.warning("Unexpected but recoverable condition")
logger.error("Error that prevents operation")

# Structured logging for events
event_logger.info(json.dumps({
    "phase": "signal_generation",
    "symbol": symbol,
    "interval": interval,
    "result": "success",
    "timestamp": datetime.utcnow().isoformat()
}))
```

### Database Best Practices
- Always use parameterized queries (avoid SQL injection)
- Close connections in finally blocks or use context managers
- Use transactions for multi-step operations
- Add appropriate indexes for query performance
- Use UNIQUE constraints to prevent duplicates

### Error Handling
```python
try:
    # Operation
    result = risky_operation()
except SpecificException as e:
    logger.error(f"Operation failed: {e}")
    # Graceful degradation
except Exception as e:
    logger.exception(f"Unexpected error: {e}")
    # Re-raise or handle
```

---

## 🔍 NEXT STEPS & ACTION ITEMS

### Immediate (Critical)
1. ⚠️ **Diagnose Signal Generation Failure**
   - [ ] Verify fetch_1h job is writing to ohlcv_raw table
   - [ ] Check Tiingo API connectivity and response format
   - [ ] Add detailed logging in TiingoFetcher.fetch_ohlcv()
   - [ ] Validate symbol naming (EURUSD vs eurusd vs EUR/USD)
   - [ ] Test manual data fetch to isolate issue

2. ⚠️ **Populate Database with Initial Data**
   - [ ] Force fetch_1h job execution: `asyncio.run(scheduler.fetch_tiingo_data('1h'))`
   - [ ] Verify ohlcv_raw has > 0 records after fetch
   - [ ] Generate features: `asyncio.run(scheduler.eod_pipeline_job())`
   - [ ] Confirm features table populated

3. ⚠️ **Validate Signal Generation Pipeline**
   - [ ] Test generate_signal() with real data
   - [ ] Verify ml_signals table receives records
   - [ ] Check Telegram alerts are sent
   - [ ] Monitor triggered_by field values

### Short Term (High Priority)
4. **Fix datetime.utcnow() Deprecation**
   - [ ] Replace line 249 in async_scheduler.py
   - [ ] Use `datetime.now(datetime.UTC)` instead

5. **Add Health Monitoring**
   - [ ] Create dashboard for job execution status
   - [ ] Add alerting for failed jobs (Telegram or email)
   - [ ] Track signal generation rate (signals/hour)

6. **Optimize Database Queries**
   - [ ] Add connection pooling
   - [ ] Cache frequently accessed data (symbol list, model)
   - [ ] Add query performance logging

### Medium Term (Enhancements)
7. **Improve Event Detection**
   - [ ] Add more event types (support/resistance, divergence)
   - [ ] Tune event thresholds based on backtesting
   - [ ] Implement multi-timeframe event confirmation

8. **Model Improvement**
   - [ ] Address 100% accuracy concern (likely overfit)
   - [ ] Implement cross-validation
   - [ ] Add model versioning and A/B testing
   - [ ] Track model performance metrics

9. **Backtesting Integration**
   - [ ] Connect backtest engine to ml_signals table
   - [ ] Generate performance reports
   - [ ] Optimize hyperparameters

### Long Term (Strategic)
10. **Scalability**
    - [ ] Move to PostgreSQL for better concurrency
    - [ ] Implement message queue (Redis/RabbitMQ)
    - [ ] Add horizontal scaling support

11. **Monitoring & Observability**
    - [ ] Integrate Prometheus + Grafana
    - [ ] Add distributed tracing
    - [ ] Create alerting rules

12. **Testing & CI/CD**
    - [ ] Add unit tests (pytest)
    - [ ] Add integration tests
    - [ ] Set up GitHub Actions for automated testing
    - [ ] Implement blue-green deployment

---

## 📚 REFERENCE LINKS

### Documentation
- [XGBoost Python API](https://xgboost.readthedocs.io/en/stable/python/python_api.html)
- [APScheduler Documentation](https://apscheduler.readthedocs.io/en/stable/)
- [Tiingo API Reference](https://api.tiingo.com/documentation/)
- [python-telegram-bot Docs](https://docs.python-telegram-bot.org/)

### Repository
- **GitHub**: https://github.com/Kingsots/silentAnalyst
- **Branch**: deploy/event-driven-system
- **Last Commit**: 7282fa8 (Nov 10, 2025)

### EC2 Access
```bash
# SSH Connection
ssh -i C:\Users\bigso\Downloads\opticore-key.pem ubuntu@52.90.60.32

# Service Management
sudo systemctl status opticore.service
sudo systemctl restart opticore.service
sudo systemctl stop opticore.service
sudo systemctl start opticore.service

# Logs
journalctl -u opticore.service -n 100 --no-pager
journalctl -u opticore.service -f
journalctl -u opticore.service --since "1 hour ago"
```

---

## ✅ VERIFICATION CHECKLIST

Before considering system operational:

- [ ] fetch_1h job executes successfully (check logs)
- [ ] ohlcv_raw table has > 0 records
- [ ] features table has > 0 records
- [ ] generate_signals job produces signals (ml_signals > 0)
- [ ] Telegram alerts are received
- [ ] event_monitor detects events and generates signals
- [ ] triggered_by field correctly set ('time' vs 'event:*')
- [ ] Model accuracy is reasonable (not 100%)
- [ ] Rate limits are respected (api_usage tracked)
- [ ] Service restarts automatically on failure
- [ ] No errors in systemd journal

---

## 🎓 KEY LEARNINGS

### What Works Well
✅ Event-driven architecture decouples data fetching from signal generation  
✅ SQLite sufficient for single-node deployment  
✅ APScheduler handles job orchestration reliably  
✅ Systemd auto-restart provides resilience  
✅ Timestamp sanitization prevents model inference errors  

### What Needs Improvement
⚠️ Empty database after rollback - need better backup strategy  
⚠️ Insufficient logging in data fetch pipeline  
⚠️ Model accuracy suspiciously high - requires validation  
⚠️ No monitoring dashboard - hard to diagnose issues  
⚠️ PowerShell SSH command complexity - use scripts instead  

### Lessons Learned
1. **Always backup database before git operations**
2. **Add detailed logging at every critical step**
3. **Use idempotent migrations (CREATE IF NOT EXISTS)**
4. **Test on fresh database to catch missing data scenarios**
5. **Monitor service logs continuously during deployment**

---

**END OF CONTEXT PACKAGE**  
**Generated**: November 11, 2025  
**For AI Handoff or Future Reference**
