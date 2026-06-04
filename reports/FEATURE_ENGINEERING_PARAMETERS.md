================================================================================
📊 FEATURE ENGINEERING PIPELINE - ALL PARAMETERS AND WINDOWS
================================================================================

Generated: 2026-02-17
Diagnostic: Complete scan of all rolling windows, EMA periods, RSI periods, lag depths, ATR periods
Status: Verified


================================================================================
FEATURE ENGINEERING PARAMETERS (From config.py & features/engine.py)
================================================================================

1. EMA (Exponential Moving Averages)
   ──────────────────────────────────
   Location: core/indicators.py line 75 & features/engine.py line 209-210
   
   • EMA_LTF (Lower Timeframe EMA):
     └─ Span: 21
     └─ Usage: ema_21 feature for short-term trend
     └─ Calculation: prices.ewm(span=21, adjust=False).mean()
   
   • EMA_HTF (Higher Timeframe EMA):
     └─ Span: 100
     └─ Usage: ema_100 feature for long-term trend filter
     └─ Calculation: prices.ewm(span=100, adjust=False).mean()


2. RSI (Relative Strength Index)
   ──────────────────────────────
   Location: core/indicators.py line 20-49 & features/engine.py line 213
   
   • RSI_PERIOD:
     └─ Period: 14
     └─ Usage: rsi_14 feature
     └─ Calculation: gain.rolling(window=14).mean() / loss.rolling(window=14).mean()


3. Volume Features
   ────────────────
   Location: core/indicators.py line 85-101 & features/engine.py line 216-219
   
   • VOLUME_PERIOD (Volume SMA Period):
     └─ Period: 20
     └─ Usage: volume_sma_20 feature
     └─ Calculation: df['volume'].rolling(window=20).mean()
   
   • volume_ratio:
     └─ Calculation: volume / volume_sma_20


4. OBV (On-Balance Volume)
   ────────────────────────
   Location: features/engine.py line 62-77
   
   • OBV:
     └─ Calculation: (volume * sign(close - close.shift(1))).cumsum()
     └─ Rolling window: None (cumulative)
     └─ Feature: obv


5. A/D (Accumulation/Distribution Line)
   ─────────────────────────────────────
   Location: features/engine.py line 82-105
   
   • A/D Line:
     └─ CLV = ((close - low) - (high - close)) / (high - low)
     └─ A/D = (CLV * volume).cumsum()
     └─ Rolling window: None (cumulative)
     └─ Feature: ad


6. VWAP (Volume Weighted Average Price)
   ────────────────────────────────────
   Location: features/engine.py line 110-138
   
   • VWAP:
     └─ Typical_Price = (high + low + close) / 3
     └─ VWAP = cumsum(typical_price * volume) / cumsum(volume)
     └─ Rolling window: None (cumulative)
     └─ Feature: vwap
   
   • VWAP_SLOPE (5-period):
     └─ Slope: vwap.pct_change(periods=5)
     └─ Period: 5
     └─ Usage: vwap_slope feature (rate of change)
     └─ Feature: vwap_slope


7. ATR (Average True Range)
   ────────────────────────
   Location: core/indicators.py line 105-141
   
   • ATR:
     └─ TR = max(high - low, abs(high - close.shift()), abs(low - close.shift()))
     └─ ATR = TR.rolling(window=14).mean()
     └─ Period: 14
     └─ Usage: Trade level calculations (entry, stop loss, take profit)


8. Volatility (Standard Deviation)
   ──────────────────────────────
   Location: core/indicators.py line 143-168
   
   • Volatility:
     └─ Returns = close.pct_change()
     └─ Volatility = returns.std() (over period)
     └─ Period: 20
     └─ Usage: Feature calculations


9. Lag Features (CRITICAL FOR MODEL)
   ──────────────────────────────────
   Location: features/engine.py line 255-258
   
   • Lag Depth: 1 bar
   └─ All ML features are shifted by 1 to prevent lookahead bias
   └─ Features lagged: ema_21_lag1, ema_100_lag1, rsi_14_lag1, 
      obv_lag1, ad_lag1, vwap_slope_lag1, volume_sma_20_lag1, volume_ratio_lag1


10. Daily EMA (Long-term Context)
    ─────────────────────────────
    Location: features/engine.py line 37-50 & features/engine.py line 240
    
    • Daily EMA:
      └─ Resampling: Daily (D)
      └─ EMA span: 100 (configurable in compute_daily_ema)
      └─ Usage: Multi-timeframe context


================================================================================
MAXIMUM WINDOW/PERIOD FOUND ACROSS ENTIRE PIPELINE
================================================================================

Parameter Type              Window/Period       Location
─────────────────────────────────────────────────────
EMA (longest):              100                 EMA_HTF (core/config.py line 30)
RSI Period:                 14                  core/config.py line 33
Volume Period:              20                  core/config.py line 38  
ATR Period:                 14                  core/indicators.py line 108
Volatility Period:          20                  core/indicators.py line 149
VWAP Slope Period:          5                   features/engine.py line 236
Lag Depth:                  1                   features/engine.py line 255

🔴 MAXIMUM VALUE: 100 (EMA_HTF - Higher Timeframe EMA)
   └─ This means the feature engine needs at least 100 bars of history
      to properly warm up the EMA_100 indicator


================================================================================
CRITICAL IMPLICATION FOR EVENT-DRIVEN SIGNALS
================================================================================

The maximum rolling window is 100 bars (EMA_100).

This means:
  ✅ Feature calculation REQUIRES minimum 100 rows of data
  ❌ If get_latest_features() returns < 100 rows, some features will be NaN
  ⚠️  If get_latest_features() returns 1-2 rows, ALL lagged features will be NaN

The prepare_features_for_inference() expects to shift by 1:
  ├─ With >= 2 rows: lag1 shift works, only first row is NaN
  ├─ With 1 row: lag1 shift moves that single row out of bounds → all NaN
  └─ With 0 rows: No data at all

Event-driven signals calling get_latest_features(lookback=30):
  └─ Should return 31 rows (30 + 1 for lag)
  └─ But if ticker/interval has limited history, might return 1-2 rows
  └─ Then all lag1 features become NaN
  └─ Then predict_signal() returns NEUTRAL (0.0)


================================================================================
FEATURE SNAPSHOT CONTENT (What's stored in database)
================================================================================

From generate_signal() in xgb_signal_engine_ec2.py line 535-565:

Raw features stored (non-lag):
├─ OHLCV: open, high, low, close, volume
├─ Indicators: ema_21, ema_100, rsi_14
├─ Volume: volume_sma_20, volume_ratio
└─ Advanced: obv, ad, vwap, vwap_slope

Lag1 features: NOT stored in snapshot
└─ Lag1 features are created in prepare_features_for_inference() 
   BEFORE model inference
└─ This allows recreating lag1 on-the-fly if needed


================================================================================
DATA REQUIREMENTS SUMMARY
================================================================================

For proper feature calculation:
┌────────────────────────────────────────────────────────────┐
│ MINIMUM HISTORICAL ROWS NEEDED:                            │
│                                                             │
│ For EMA_100 warmup:     100+ rows                          │
│ For lag features:       100+ rows + 1 (for shift)         │
│ For model inference:    2 rows minimum (1 for shift, 1 to use)
│                                                             │
│ RECOMMENDED FOR EVENTS: 30+ rows (lookback=30)            │
│ MINIMUM FOR EVENTS:     2 rows (fallback)                 │
└────────────────────────────────────────────────────────────┘

Current issue: Event-driven signals receiving < 2 rows
Result: Lag1 features all NaN → predict_signal returns NEUTRAL


================================================================================
