# OptiCore Bot - Quick Start Guide

## ✅ Steps 1-6 Complete!

### What's Been Built:
- ✅ **Core System**: Config, Indicators, Multi-Timeframe Analysis, Database
- ✅ **Strategy**: OptiCore strategy matching your Pine Script (EMA 21/100, RSI 14, strict engulfing, volume 1.2x)
- ✅ **Data Layer**: CSV loader, Yahoo Finance fetcher, unified database
- ✅ **Alert System**: Telegram bot, signal tracker (NEW/CONTINUATION), dashboard formatter
- ✅ **Main Bot**: Full orchestration (fetch → analyze → filter → alert)
- ✅ **Scheduler**: Automated runs every 30m and 1h

---

## 🚀 How to Run

### 1. Configure Environment (.env file)
Make sure your `.env` file has:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

**To get Telegram credentials:**
1. Create bot with [@BotFather](https://t.me/botfather)
2. Get chat ID from [@userinfobot](https://t.me/userinfobot)

---

### 2. One-Time Manual Run
Test the system with a single execution:

```powershell
C:/Users/bigso/Downloads/ML/venv/Scripts/python.exe main_bot.py
```

This will:
- Fetch data for all 13 symbols
- Analyze on both 30m and 1h timeframes
- Check multi-timeframe cascade (Daily → 4H → 2H → 1H → 30m)
- Send NEW alerts via Telegram
- Save signals to database

---

### 3. Automated Scheduler
Run the bot continuously on schedule:

```powershell
C:/Users/bigso/Downloads/ML/venv/Scripts/python.exe scheduler.py
```

**Schedule (from config):**
- Every 30 minutes → checks 30m timeframe
- Every 60 minutes → checks 1h timeframe

**To stop:** Press `Ctrl+C`

---

### 4. Test Telegram Connection
Quick test to verify Telegram setup:

```python
from alerts.telegram_bot import TelegramBot

bot = TelegramBot()
bot.send_test_message()
```

---

## 📊 What the Bot Does

### For Each Symbol:
1. **Fetch Data** (priority: CSV → Database → Yahoo Finance)
   - Daily, 4H, 2H, 1H, 30m timeframes

2. **Check LONG Conditions** (all must be TRUE):
   - ✅ Strict bullish engulfing pattern
   - ✅ Close > EMA(21)
   - ✅ RSI > 50
   - ✅ Volume > 1.2x average
   - ✅ Daily close > Daily EMA(100)
   - ✅ All timeframes aligned bullish

3. **Check SHORT Conditions** (all must be TRUE):
   - ✅ Strict bearish engulfing pattern
   - ✅ Close < EMA(21)
   - ✅ RSI < 50
   - ✅ Volume > 1.2x average
   - ✅ Daily close < Daily EMA(100)
   - ✅ All timeframes aligned bearish

4. **Filter by Confidence**
   - Must be ≥ 65% (configurable in `Config.TARGET_EFFICIENCY`)

5. **Track Signal State**
   - **NEW**: First time signal detected → immediate alert
   - **CONTINUATION**: Same signal re-confirmed after 1 hour → alert again
   - **SKIP**: Same signal within 1 hour → no duplicate alert

6. **Send Telegram Alert** (rich dashboard format)
   - Signal emoji (🟢 LONG / 🔴 SHORT)
   - Entry conditions checklist
   - Price, EMA, RSI, Volume
   - Daily HTF trend
   - Multi-timeframe cascade visualization
   - Confidence score

7. **Save to Database**
   - Signal history
   - OHLCV data
   - Performance tracking

---

## 📁 Project Structure

```
ML/
├── core/               # Core logic
│   ├── config.py       # Configuration (EMA 21/100, RSI 14, watchlist)
│   ├── indicators.py   # Technical indicators
│   ├── multi_timeframe.py  # Cascade analyzer
│   └── database.py     # SQLite manager
│
├── strategies/         # Trading strategies
│   ├── opticore_strategy.py  # Main strategy
│   ├── entry_rules.py  # LONG/SHORT conditions
│   └── volume_filter.py  # Volume spike detection
│
├── data/              # Data handling
│   ├── csv_loader.py   # Load CSV files
│   ├── fetcher.py      # Multi-source data fetcher
│   └── generator.py    # Generate 30m data
│
├── alerts/            # Alert system
│   ├── telegram_bot.py  # Telegram API
│   ├── signal_tracker.py  # NEW vs CONTINUATION
│   └── formatter.py    # Dashboard formatting
│
├── utils/             # Utilities
│   └── logger.py       # Centralized logging
│
├── backtest/          # Backtesting (Step 7 - pending)
│
├── main_bot.py        # Main orchestrator
├── scheduler.py       # Automated scheduler
├── generate_30m_data.py  # Fetch 30m data
├── test_implementation.py  # Test all components
│
├── data_files/        # CSV data
├── trading_bot.db     # SQLite database
└── signal_state.json  # Signal tracker state
```

---

## 🔧 Configuration Options

Edit `core/config.py` to customize:

### Strategy Settings
- `EMA_LTF = 21` - Lower timeframe EMA
- `EMA_HTF = 100` - Daily EMA
- `RSI_PERIOD = 14` - RSI period
- `RSI_LONG_THRESHOLD = 50` - RSI threshold for longs
- `RSI_SHORT_THRESHOLD = 50` - RSI threshold for shorts
- `VOLUME_MULTIPLIER = 1.2` - Volume spike threshold
- `STRICT_ENGULFING = True` - Use strict engulfing patterns

### Timeframes
- `ENTRY_TIMEFRAMES = ['30m', '1h']` - Timeframes to monitor
- `CASCADE_TIMEFRAMES = ['1d', '4h', '2h', '1h', '30m']` - Cascade alignment
- `HTF_TIMEFRAME = '1d'` - Higher timeframe filter

### Alerts
- `ALERT_NEW_SIGNALS = True` - Send NEW signals
- `ALERT_CONTINUATION_SIGNALS = True` - Send CONTINUATION signals
- `CONTINUATION_ALERT_INTERVAL = 3600` - Seconds between continuation alerts (1 hour)

### Performance
- `TARGET_EFFICIENCY = 0.65` - Minimum 65% confidence
- `BACKTEST_DAYS = 90` - Backtesting period

---

## 📝 Logs

All activity logged to: `opticore_bot.log`

Log levels:
- **INFO**: Normal operations, signals sent
- **WARNING**: Missing data, skipped signals
- **ERROR**: API failures, configuration issues
- **DEBUG**: Detailed execution flow

---

## 🎯 What's Next (Step 7)

### Pending:
1. **Backtest Engine** - Test strategy on historical data
2. **Performance Metrics** - Calculate win rate, profit factor, drawdown
3. **Final Integration Test** - End-to-end validation

### To Complete Step 7:
```powershell
# Will create:
# - backtest/engine.py
# - backtest/metrics.py
# - Validation script
```

---

## 🆘 Troubleshooting

### No Telegram Alerts?
1. Check `.env` file has correct `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
2. Run test: `bot.send_test_message()`
3. Check logs: `opticore_bot.log`

### No Data Found?
1. Check CSV files in `data_files/` folder
2. Try force refresh: `bot.run(force_refresh=True)`
3. Generate 30m data: `python generate_30m_data.py`

### Low Confidence Signals?
1. Check if all 5 entry conditions are met
2. Verify multi-timeframe cascade alignment
3. Lower threshold in `Config.TARGET_EFFICIENCY`

### Duplicate Alerts?
- Tracker prevents duplicates within 1 hour
- Check `signal_state.json` for active signals
- Delete file to reset tracker

---

## 📊 Database Queries

Useful SQL queries for `trading_bot.db`:

```sql
-- View recent signals
SELECT * FROM signals ORDER BY timestamp DESC LIMIT 10;

-- Count signals by symbol
SELECT symbol, COUNT(*) as count 
FROM signals 
GROUP BY symbol 
ORDER BY count DESC;

-- Signals by type
SELECT signal_type, COUNT(*) as count 
FROM signals 
GROUP BY signal_type;

-- Check data availability
SELECT symbol, timeframe, COUNT(*) as records 
FROM ohlcv_data 
GROUP BY symbol, timeframe;
```

---

## 🎉 You're All Set!

Your OptiCore bot is ready to:
- ✅ Monitor 13 symbols (US30, XAUUSD, 11 forex pairs)
- ✅ Analyze 30m and 1h entry timeframes
- ✅ Verify Daily → 4H → 2H → 1H → 30m cascade alignment
- ✅ Send rich Telegram alerts with dashboard formatting
- ✅ Track NEW vs CONTINUATION signals
- ✅ Run automatically on schedule

**Start with:** `python main_bot.py` for a test run!
