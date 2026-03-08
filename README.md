# OptiCore Trading Bot

🚀 **Multi-Timeframe Trading Alert System** matching your TradingView Pine Script strategy.

## 📊 Strategy Overview

**OptiCore Strategy** - A strict rule-based trading system with multi-timeframe confluence.

### Core Settings
- **EMA Periods:** 21 (Lower Timeframe), 100 (Daily HTF)
- **RSI Period:** 14
- **Volume Filter:** 1.2x average (20-period SMA)
- **Engulfing:** Strict patterns required
- **Entry Timeframes:** 30-minute and 1-hour
- **HTF Filter:** Daily timeframe alignment mandatory

### Entry Rules

#### LONG Signal Requirements (ALL must be TRUE):
1. ✅ Strict bullish engulfing pattern
2. ✅ Close > EMA(21)
3. ✅ RSI > 50
4. ✅ Volume > 1.2x average
5. ✅ Daily close > Daily EMA(100)

#### SHORT Signal Requirements (ALL must be TRUE):
1. ✅ Strict bearish engulfing pattern
2. ✅ Close < EMA(21)
3. ✅ RSI < 50
4. ✅ Volume > 1.2x average
5. ✅ Daily close < Daily EMA(100)

### Multi-Timeframe Cascade
All timeframes must align: **Daily → 4H → 2H → 1H → 30m**

---

## 📁 Project Structure

```
ML/
├── core/                          # Core components
│   ├── config.py                  # Configuration (EMA 21/100, watchlist, etc.)
│   ├── indicators.py              # Technical indicators (RSI, EMA, Volume)
│   ├── multi_timeframe.py         # Cascade analysis
│   └── database.py                # SQLite database manager
│
├── strategies/                    # Trading strategies
│   ├── opticore_strategy.py       # Main strategy matching Pine Script
│   ├── entry_rules.py             # Entry conditions (strict engulfing, etc.)
│   └── volume_filter.py           # Volume spike detection
│
├── data/                          # Data management
│   ├── fetcher.py                 # Multi-source data fetcher
│   ├── csv_loader.py              # CSV file loader
│   └── generator.py               # 30m data generator
│
├── alerts/                        # Alert system (TO BE IMPLEMENTED)
│   ├── telegram_bot.py            # Telegram notifications
│   ├── signal_tracker.py          # Track NEW vs CONTINUATION signals
│   └── formatter.py               # Alert formatting
│
├── backtest/                      # Backtesting (TO BE IMPLEMENTED)
│   ├── engine.py                  # Backtest engine
│   └── metrics.py                 # Performance metrics
│
├── utils/                         # Utilities
│   └── logger.py                  # Logging setup
│
├── archive/                       # Old bot files (archived)
│
├── data_files/                    # CSV data storage
│
├── generate_30m_data.py           # Script to fetch 30m data
├── main_bot.py                    # Main entry point (TO BE IMPLEMENTED)
├── requirements.txt               # Python dependencies
├── .env                           # Environment variables
└── README.md                      # This file
```

---

## 🛠️ Installation & Setup

### 1. Prerequisites
- Python 3.8 or higher
- pip package manager

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create/edit `.env` file:

```env
# Telegram Bot Credentials
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# API Keys (Optional)
ALPHA_VANTAGE_API_KEY=your_key_here
TWELVE_DATA_API_KEY=your_key_here
```

### 4. Organize Your CSV Files

Move all CSV files to `data_files/` directory:

```powershell
# Move CSV files
Move-Item *.csv data_files/
```

Expected CSV format:
- Columns: `timestamp`, `open`, `high`, `low`, `close`, `volume`
- Filename pattern: `{SYMBOL}_{TIMEFRAME}.csv` (e.g., `US30_1h.csv`)

### 5. Generate Missing 30-Minute Data

```powershell
python generate_30m_data.py
```

This will fetch actual 30m data from Yahoo Finance for your watchlist.

---

## 🎯 Watchlist

Currently configured symbols:

**Indices:**
- US30 (Dow Jones)

**Commodities:**
- XAUUSD (Gold)

**Forex Majors:**
- USDJPY, GBPUSD, EURUSD, AUDUSD, USDCAD

**Forex Crosses:**
- AUDJPY, GBPJPY, CADJPY, EURJPY, EURGBP, AUDCAD

**To modify watchlist:** Edit `core/config.py` → `WATCHLIST` dictionary

---

## 📈 Usage (Steps 1-3 Completed)

### ✅ Step 1: Architecture Setup (DONE)
- Clean folder structure created
- All core modules implemented
- Modular, maintainable code

### ✅ Step 2: Core Implementation (DONE)
- Configuration matching Pine Script
- Technical indicators (RSI, EMA, Volume)
- Multi-timeframe cascade logic
- Database management

### ✅ Step 3: Strategy Implementation (DONE)
- OptiCore strategy matching Pine Script exactly
- Entry rules with strict engulfing
- Volume filter (1.2x detection)
- Data fetching and CSV loading

### 🔄 Next Steps (Steps 4-7):
4. **Alert System** - Telegram notifications with signal tracking
5. **Main Bot** - Orchestrate strategy across watchlist
6. **Scheduler** - Run every 30m and 1h
7. **Backtesting** - Validate strategy performance

---

## 🧪 Testing the Implementation

### Test Configuration

```python
python -c "from core.config import Config; Config.print_config()"
```

### Test Data Loading

```python
from data.csv_loader import CSVLoader
from core.config import Config

loader = CSVLoader()

# Check available symbols
symbols = loader.get_available_symbols()
print(f"Available symbols: {symbols}")

# Load data for US30
data = loader.load_all_timeframes('US30')
print(f"Loaded timeframes: {list(data.keys())}")
```

### Test Strategy

```python
from strategies.opticore_strategy import OptiCoreStrategy
from data.fetcher import DataFetcher

strategy = OptiCoreStrategy()
fetcher = DataFetcher()

# Fetch all timeframes for US30
data = fetcher.fetch_all_timeframes('US30')

# Analyze
result = strategy.analyze_symbol('US30', '1h', data)
print(strategy.format_signal_summary(result))
```

---

## 📊 Configuration

### Key Settings (in `core/config.py`)

```python
# EMA Settings
EMA_LTF = 21          # Lower timeframe EMA
EMA_HTF = 100         # Daily EMA

# RSI Settings
RSI_PERIOD = 14
RSI_LONG_THRESHOLD = 50
RSI_SHORT_THRESHOLD = 50

# Volume Filter
VOLUME_PERIOD = 20
VOLUME_MULTIPLIER = 1.2

# Engulfing Pattern
STRICT_ENGULFING = True    # Require strict engulfing

# Timeframes
ENTRY_TIMEFRAMES = ['30m', '1h']
CASCADE_TIMEFRAMES = ['1d', '4h', '2h', '1h', '30m']
HTF_TIMEFRAME = '1d'       # Daily trend filter

# Backtest Targets
TARGET_EFFICIENCY = 0.65    # 65% win rate
```

---

## 🔄 Data Sources

### Priority Order:
1. **CSV Files** (Primary) - Fastest, stored locally
2. **Database Cache** (Secondary) - Recent data
3. **Yahoo Finance** (Fallback) - Live data fetching

### Supported Timeframes:
- Daily (1d)
- 4-Hour (4h)
- 2-Hour (2h)
- 1-Hour (1h)
- 30-Minute (30m)

---

## 📝 Changelog

### Phase 1-3 Implementation (Current)
- ✅ Created clean modular architecture
- ✅ Implemented core configuration (EMA 21/100, RSI 14)
- ✅ Built technical indicators matching Pine Script
- ✅ Multi-timeframe cascade analyzer
- ✅ Unified database with timeframe support
- ✅ OptiCore strategy with exact Pine Script logic
- ✅ Entry rules with strict engulfing patterns
- ✅ Volume filter (1.2x spike detection)
- ✅ CSV loader supporting all timeframes
- ✅ Multi-source data fetcher (CSV → DB → Yahoo)
- ✅ 30m data generator with Yahoo Finance API

### From Previous (Archived)
- Multiple duplicate bots (archived)
- Inconsistent logic across files
- No multi-timeframe analysis
- Wrong EMA periods (12/26 instead of 21/100)
- Inverted RSI logic
- No volume filtering

---

## 🎓 Pine Script to Python Mapping

| Pine Script | Python Equivalent |
|-------------|-------------------|
| `ta.ema(close, 21)` | `TechnicalIndicators.calculate_ema(df['close'], 21)` |
| `ta.rsi(close, 14)` | `TechnicalIndicators.calculate_rsi(df['close'], 14)` |
| `ta.sma(volume, 20)` | `TechnicalIndicators.calculate_sma(df['volume'], 20)` |
| `close > open` | `TechnicalIndicators.is_bullish_candle(df)` |
| Strict engulfing | `TechnicalIndicators.is_strict_bullish_engulfing(df)` |
| `request.security(..., "D", ...)` | `MultiTimeframeAnalyzer.check_htf_trend(daily_df)` |

---

## 🐛 Troubleshooting

### "No CSV files found"
- Ensure CSV files are in `data_files/` directory
- Check filename format: `{SYMBOL}_{TIMEFRAME}.csv`

### "Missing 30m data"
- Run `python generate_30m_data.py`
- Requires yfinance: `pip install yfinance`

### "Module not found"
- Install dependencies: `pip install -r requirements.txt`
- Ensure you're in the correct directory

### "Database locked"
- Close any open database connections
- Delete `trading_bot.db` and restart (data will be reloaded from CSV)

---

## 📞 Support

- Check logs: `opticore_bot.log`
- Review configuration: `Config.print_config()`
- Validate data: `DataFetcher.get_data_status()`

---

## 📄 License

Private project - All rights reserved.

---

**Built with precision. Trades with confidence.** 🚀
