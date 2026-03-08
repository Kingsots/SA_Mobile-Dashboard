# Event-Driven System - Complete Logic Deep Dive

## Overview
The event-driven trading system continuously monitors forex OHLCV data for **market inflection points** (events) that trigger ML signal generation. Each event type represents a distinct market condition requiring attention.

---

## Event Detection Architecture

```
Market Data (OHLCV)
        ↓
    EventMonitor (orchestrator)
        ↓
    ├─ Structure Detector (3 triggers)
    ├─ Momentum Detector (2 triggers)
    ├─ Volume/Volatility Detector (2 triggers)
        ↓
    EventFilter (confidence + cooldown)
        ↓
    ML Signal Engine (XGBoost)
        ↓
    Telegram Alert
```

---

## All Event Triggers (7 Total)

### **1. STRUCTURE DETECTION** (Market Structure Module)
Detects price pattern breaks and inflection points.

#### A. **Higher-High Breakout** → `trendline_break_resistance`
- **What it detects:** Current candle high exceeds recent peak
- **Trigger:** `latest_high > (reference_high × (1 + min_break_ratio))`
- **Parameters:**
  - `lookback = 20` candles (reference period)
  - `min_break_ratio = 0.0005` (0.05% break threshold for forex 1h)
- **Confidence:** Scales from 0.2 to 0.95 based on break magnitude
- **Expected:** Bullish breakout - price breaking above resistance
- **Status:** ❌ **NOT DETECTING** (0 events in 11 hours)

**Why not detecting?**
```
Reference High: e.g., 1.34700
Latest High: 1.34703
Break ratio: (1.34703 - 1.34700) / 1.34700 = 0.000022 = 0.0022%
Threshold: 0.0005 = 0.05%
Result: 0.0022% < 0.05% → NO TRIGGER
```
Forex 1h candles have small ranges; 0.05% is still too strict.

#### B. **Lower-Low Breakdown** → `trendline_break_support`
- **What it detects:** Current candle low breaks below recent support
- **Trigger:** `latest_low < (reference_low × (1 - min_break_ratio))`
- **Parameters:** Same as Higher-High
- **Confidence:** 0.2 to 0.95
- **Expected:** Bearish breakdown - price breaking below support
- **Status:** ❌ **NOT DETECTING** (0 events in 11 hours)

#### C. **Structure Shift** → `structure_shift`
- **What it detects:** Higher highs AND higher lows (uptrend) or lower highs AND lower lows (downtrend)
- **Trigger:** Pattern sequence in last 5 candles
- **Confidence:** Fixed 0.50
- **Expected:** Trend initiation confirmation
- **Status:** ❌ **NOT DETECTING** (likely no clear trend sequences in recent data)

---

### **2. MOMENTUM DETECTION** (Momentum Confirmation Module)
Detects changes in price momentum and oscillator extremes.

#### A. **RSI Rebound (Bullish)** → `rsi_rebound_bullish` ✅ WORKING
- **What it detects:** RSI emerging from oversold zone
- **Trigger Conditions:**
  - `prev_rsi < 30` (oversold threshold)
  - `current_rsi > (prev_rsi + 5)` (rebound of 5+ points)
- **Parameters:**
  - `period = 14`
  - `oversold = 30`
  - `rebound_threshold = 5`
- **Confidence:** Scales from 0.4 to 0.9 based on depth of oversold (how far below 30)
- **Example:** 
  - Prev RSI: 25 (deep oversold)
  - Current RSI: 32 (rebounded 7 points)
  - → TRIGGER: `rsi_rebound_bullish` with high confidence
- **Status:** ✅ **WORKING** (13 signals detected)
- **Real signals observed:**
  - Dec 31 22:49 - AUDUSD
  - Dec 31 01:04 - EURGBP
  - Dec 31 03:04 - USDJPY
  - Dec 31 04:04 - GBPUSD
  - Dec 31 05:04 - XAUUSD, AUDUSD
  - Dec 31 08:04 - EURUSD, AUDUSD

#### B. **RSI Rejection (Bearish)** → `rsi_rejection_bearish` ✅ WORKING
- **What it detects:** RSI falling from overbought zone
- **Trigger Conditions:**
  - `prev_rsi > 70` (overbought threshold)
  - `current_rsi < (prev_rsi - 5)` (rejection of 5+ points)
- **Parameters:**
  - `period = 14`
  - `overbought = 70`
  - `rejection_threshold = 5`
- **Confidence:** Scales from 0.4 to 0.9 based on depth of overbought (how far above 70)
- **Example:**
  - Prev RSI: 78 (deep overbought)
  - Current RSI: 71 (rejected 7 points)
  - → TRIGGER: `rsi_rejection_bearish` with high confidence
- **Status:** ✅ **WORKING** (7 signals detected)
- **Real signals observed:**
  - Dec 31 01:04 - EURGBP
  - Dec 31 03:04 - USDJPY, CADJPY
  - Dec 31 08:04 - USDCAD
  - Dec 31 09:14 - USDCAD
  - Dec 31 10:24 - USDCAD

---

### **3. VOLUME & VOLATILITY DETECTION** (Volume/Volatility Module)

#### A. **Volume Spike** → `volume_spike`
- **What it detects:** Abnormal volume surge above historical average
- **Trigger:** `current_volume > (avg_volume × ratio_threshold)`
- **Parameters:**
  - `window = 20` candles (historical baseline)
  - `ratio_threshold = 1.5` (50% above average)
- **Confidence:** 0.3 to 0.95 based on spike magnitude
- **Expected:** Volume confirmation of price move
- **Status:** ❌ **NOT DETECTING** (forex typically low volume, synthetic)

#### B. **Volatility Expansion (ATR)** → `volatility_expansion` ✅ WORKING
- **What it detects:** Current ATR significantly higher than baseline
- **Trigger:** `recent_atr > (baseline_atr × expansion_ratio)`
- **Parameters:**
  - `period = 14` (ATR calculation)
  - `expansion_ratio = 1.3` (30% above baseline)
  - Baseline = average ATR of last 13 candles
  - Recent ATR = current (14th) candle's ATR
- **Confidence:** 0.3 to 0.9 based on expansion magnitude
- **Example:**
  - Baseline ATR: 0.0008
  - Recent ATR: 0.00115
  - Ratio: 1.4375 (43.75% expansion)
  - → TRIGGER: `volatility_expansion` with ~0.70 confidence
- **Status:** ✅ **WORKING** (3 new signals at Dec 31 13:03 UTC)
- **Real signals observed (Dec 31 13:03 UTC):**
  - GBPUSD: conf=0.54, ATR ratio=1.352
  - EURUSD: conf=0.51, ATR ratio=1.319
  - EURGBP: conf=0.51, ATR ratio=1.311

#### C. **EMA Crossover** → `ema_cross_bullish` / `ema_cross_bearish`
- **What it detects:** Fast EMA crossing above/below slow EMA
- **Trigger:**
  - Bullish: `fast_prev < slow_prev AND fast_now > slow_now`
  - Bearish: `fast_prev > slow_prev AND fast_now < slow_now`
- **Parameters:**
  - `fast_span = 21`
  - `slow_span = 100`
  - `separation_threshold = 0.001` (0.1%)
- **Confidence:** 0.4 to 0.9 based on EMA separation distance
- **Status:** ❌ **NOT DETECTING** (EMA crossing patterns rare in range-bound forex)

---

## Event Detection Pipeline Flow

```
1. OHLCV Data Retrieved (1h candles for 12 symbols)
   ↓
2. For Each Symbol:
   a. Run Structure Detectors (3 checks)
   b. Run Momentum Detectors (2 checks)
   c. Run Volume/Volatility Detectors (2 checks)
   ↓
3. Filter Events:
   - Check confidence ≥ 0.50 (minimum)
   - Apply cooldown (3600 seconds = 1 hour per symbol)
   - De-duplicate same event types
   ↓
4. For Each Triggered Event:
   - Generate ML features from market data
   - Run XGBoost model
   - Generate BUY/SELL signal
   - Calculate Entry/SL/TP levels
   ↓
5. Send Telegram Alert:
   - Format: emoji + symbol + signal + confidence + levels
   - Real-time notification to @opticore_trading_signals
```

---

## Why Events Work / Don't Work

### ✅ RSI & Volatility WORKING
- **Reason:** Based on oscillators and volatility measures
- **Data required:** Only needs recent price action
- **Stability:** RSI oversold/overbought zones are reliable in ranging markets
- **Frequency:** Happens regularly (13+7+3 = 23 events in 11 hours = ~2 per hour)

### ❌ Structure Breakouts NOT WORKING
- **Reason:** 0.05% threshold still too high for forex pip-scale movements
- **Example:** EURUSD 1h move might be 10 pips = 0.0010 (0.10%)
  - To hit 0.05% threshold needs 5 pips above reference
  - This is rare and easily retraced
- **The problem:** Forex doesn't have "clean" breakouts like stock charts
  - Price moves in small increments
  - High liquidity creates immediate counters
  - No gap moves (continuous 24h market)

### ❌ EMA Crossover & Volume Spike NOT WORKING
- **EMA:** 100-period slow EMA rarely crosses 21-period fast EMA in 1h timeframe
- **Volume:** Forex is synthetic/ECN, not exchange-based; volume not reliable

---

## Current Configuration (FROZEN v1.0)

```python
# core/config.py
TELEGRAM_SEND_EVENT_ALERTS = True  # ✅ Enabled

# signals/event_monitor.py - EventMonitorConfig
min_confidence: float = 0.50              # Relaxed from 0.55
cooldown_seconds: int = 3600              # 1 hour per symbol
structure_lookback: int = 20              # Candles
volume_window: int = 20                   # Candles
atr_period: int = 14                      # ATR calculation
ema_fast: int = 21                        # Fast EMA
ema_slow: int = 100                       # Slow EMA
rsi_period: int = 14                      # RSI calculation
min_breakout_ratio: float = 0.0005         # 0.05% (was 0.15%)
```

---

## Signal Generation After Event Trigger

Once an event is detected and passes the filter:

1. **Fetch Features:** Extract 50+ technical indicators from market data
2. **XGBoost Model:** Inference with features
3. **Output:**
   - `signal`: 1 (BUY), -1 (SELL), 0 (NEUTRAL)
   - `confidence`: 0.0-1.0 (model probability)
4. **Entry/SL/TP Calculation:**
   - Entry: Current ask/bid (event price)
   - Stop Loss: Previous swing low/high (-2%)
   - Take Profit: Risk:Reward 1:2 ratio

**Database Storage:** ml_signals table with `triggered_by = 'event:rsi_rebound_bullish'` etc.

---

## What's Currently Happening (First Week)

### Signal Distribution
- **Total:** 1,513 signals in 11 hours
- **Event-driven:** 23 (1.5%)
  - RSI Rebound Bullish: 13 ✅
  - RSI Rejection Bearish: 7 ✅
  - Volatility Expansion: 3 ✅
- **Time-based fallback:** 1,490 (98.5%) - database only, NOT alerted

### Telegram Delivery
- ✅ 6 messages sent at 13:03:40-13:03:41 UTC (3 volatility events)
- ✅ 100% delivery rate confirmed in logs
- ✅ Format includes: emoji, ticker, signal, confidence, entry/SL/TP

---

## Next Steps for Deep Understanding

To investigate further:

1. **Why structure breakouts disabled?**
   - Option A: Reduce threshold to 0.02% or lower
   - Option B: Use different pattern detection (SAR, Donchian, etc.)
   - Option C: Disable entirely, rely on RSI + volatility only

2. **Why EMA not triggering?**
   - Option A: Reduce slow span (100 → 50)
   - Option B: Remove EMA crossover (not useful for 1h forex)

3. **Why volume spike not triggering?**
   - Option A: Forex has no real volume; remove this detector
   - Option B: Use price-based volume (tick-based approximation)

4. **Should we use other detectors?**
   - Bollinger Band breakouts
   - MACD histogram crosses
   - Stochastic divergences
   - Support/resistance touches

Would you like me to investigate any of these options or modify specific detector logic?
