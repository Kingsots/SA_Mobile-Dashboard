# Event Detection Status Matrix

## Event Detector Status Summary

| Event Type | Module | Status | Signals | Why | Fix Needed? |
|---|---|---|---|---|---|
| **rsi_rebound_bullish** | momentum_confirmation | ✅ ACTIVE | 13 | RSI emerges from oversold (<30) | No - working well |
| **rsi_rejection_bearish** | momentum_confirmation | ✅ ACTIVE | 7 | RSI falls from overbought (>70) | No - working well |
| **volatility_expansion** | volume_volatility | ✅ ACTIVE | 3 | ATR 30%+ above baseline | No - working well |
| **volume_spike** | volume_volatility | ❌ SILENT | 0 | Volume 50%+ above average | Yes - forex has no real volume |
| **trendline_break_resistance** | market_structure | ❌ SILENT | 0 | Price 0.05%+ above recent high | Yes - threshold too high |
| **trendline_break_support** | market_structure | ❌ SILENT | 0 | Price 0.05%+ below recent low | Yes - threshold too high |
| **ema_cross_bullish** | momentum_confirmation | ❌ SILENT | 0 | Fast EMA crosses above slow | Yes - rare in 1h forex |
| **ema_cross_bearish** | momentum_confirmation | ❌ SILENT | 0 | Fast EMA crosses below slow | Yes - rare in 1h forex |
| **structure_shift** | market_structure | ❌ SILENT | 0 | HH+HL or LL+LH pattern | Yes - tight entry sequence needed |

---

## Active Detectors (Working Now)

### 1. RSI Rebound Bullish ✅
```
Condition:
  prev_rsi < 30 (oversold)
  current_rsi > prev_rsi + 5 (rebound 5+ points)

Example Trigger:
  Price: GBPUSD 1.34679
  Prev RSI: 22
  Current RSI: 28
  → TRIGGER with confidence=0.78

Last 12 hours: 13 signals
Hourly rate: ~1-2 signals/hour
Telegram: ✅ Alert sent
```

### 2. RSI Rejection Bearish ✅
```
Condition:
  prev_rsi > 70 (overbought)
  current_rsi < prev_rsi - 5 (rejection 5+ points)

Example Trigger:
  Price: USDCAD 1.32456
  Prev RSI: 76
  Current RSI: 70
  → TRIGGER with confidence=0.82

Last 12 hours: 7 signals
Hourly rate: ~0.5-1 signal/hour
Telegram: ✅ Alert sent
```

### 3. Volatility Expansion ✅
```
Condition:
  recent_atr > baseline_atr × 1.3 (30% higher)

Example Trigger (Dec 31 13:03 UTC):
  Symbol: GBPUSD
  Baseline ATR (prev 13): 0.000899
  Recent ATR: 0.001215
  Ratio: 1.352 (35.2% expansion)
  Confidence: 0.54
  → TRIGGER

Recent: 3 signals in last hour
Telegram: ✅ 6 messages sent (possibly multi-part)
```

---

## Inactive Detectors (Need Investigation)

### ❌ Structure Breakouts (0 signals)

**Why Not Firing:**

```
Forex 1h typical move: ~15-25 pips
Example: EURUSD 1.17500 → 1.17525 = 25 pips = 0.21% move

Threshold: min_break_ratio = 0.0005 (0.05%)
This means: Need price > (recent_high × 1.0005)

Example scenario:
  Recent high (20 candles): 1.17620
  Current high: 1.17625
  Break needed: 1.17620 × 1.0005 = 1.17626
  Actual: 1.17625
  Result: 1.17625 < 1.17626 → NO TRIGGER

Problem: 0.05% = 5 pips on EURUSD
- Most breakouts are retraced
- Need sustainable break above 5 pips
- Rare to stay above overnight
```

**Options to Fix:**
1. Lower threshold: 0.0005 → 0.0002 (0.02% = 2 pips)
2. Use different approach: Donchian channels, SAR, Support/Resistance levels
3. Disable entirely and rely on RSI + volatility

---

### ❌ EMA Crossover (0 signals)

**Why Not Firing:**

```
Fast EMA (21) needs to cross Slow EMA (100)
In 1h timeframe:
- Fast EMA is very responsive
- Slow EMA takes 100 hours to fully adjust
- Crossovers happen but rarely

Typical pattern:
- 21 EMA crosses 100 EMA during trend
- But then stays whipsawed in consolidation
- Need separation > 0.1% to trigger

Recent data: Likely range-bound
- No sustained trend for crossover
```

**Options to Fix:**
1. Reduce slow span: 100 → 50 (more responsive)
2. Lower separation threshold
3. Use MACD instead (more stable)
4. Disable - not reliable for 1h forex

---

### ❌ Volume Spike (0 signals)

**Why Not Firing:**

```
Forex markets use ECN/synthetic execution
- No real exchange volume data available
- Tiingo "volume" may be price ticks only
- Threshold: 1.5x average spike

In synthetic forex:
- Volume changes slowly
- Spikes are rare and mild
- Hard to detect true conviction
```

**Options to Fix:**
1. Use Tick Volume instead (price change count)
2. Lower spike threshold: 1.5x → 1.2x
3. Disable - volume unreliable for forex
4. Use Volume Profile instead

---

## Recommended Actions for Next Phase

### If You Want More Event Signals:
```
1. Lower structure breakout threshold:
   0.0005 → 0.0002  (easier triggers, more false positives)

2. Add new detector:
   - Support/Resistance touches
   - Bollinger Band edges
   - MACD crossovers
   
3. Reduce EMA spans:
   Fast: 21 → 12
   Slow: 100 → 50
```

### If You Want Fewer, Higher-Quality Signals:
```
1. Raise confidence floor:
   0.50 → 0.70  (only highest confidence events)

2. Increase cooldown:
   3600 → 7200  (max 0.5 signals/hour per symbol)

3. Keep only RSI + Volatility:
   - Remove structure, EMA, volume detectors
   - Most consistent performers
```

### If You Want Better Breakout Detection:
```
1. Implement Pin Bar detection
   - Wick at top but closes lower = rejection
   - More reliable than simple breakout

2. Implement Engulfing patterns
   - Larger candle engulfs previous
   - Classic reversal pattern

3. Use support/resistance levels
   - Historical swing points
   - More meaningful than lookback
```

---

## Question for You

**Given the first week results:**

Current setup generates 23 event signals in 11 hours (best case: 50+ per day).

1. **Is this signal frequency good?** (Currently ~2/hour)
   - Too many → need stricter filters
   - Too few → need more detectors
   - Just right → keep as-is

2. **Which detector matters most?**
   - RSI momentum (most consistent)
   - Volatility (market expansion)
   - Structure (breakout confirmation)

3. **For next week, should we:**
   - Add new detectors (MACD, BB, SAR)?
   - Tune existing thresholds?
   - Focus on trade execution instead?

What's your preference?
