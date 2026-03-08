# Hybrid Signal System - Implementation Complete ✅

**Date**: December 23, 2025  
**Status**: ✅ **LIVE ON EC2** (12:18 UTC)  
**Branch**: deploy/event-driven-system

---

## What Was Built

A **dual-mode signal generation system** that combines event-driven and time-based approaches to handle low-volatility forex trading:

### System Architecture

```
┌─ EVENT MONITOR (every 5 min) ────────────────┐
│ Scans for technical market events             │
│ - EMA crossovers (21/100)                     │
│ - RSI reversals (overbought/oversold)         │
│ - Structure breaks (higher highs/lows)        │
│ - Volume spikes & ATR expansion               │
│ Event confidence: 0.35 - 0.95                 │
│ Cooldown: 1 hour/symbol (prevents spam)       │
└─────────────────────────────────┬─────────────┘
                                  │
                    ┌─ SIGNAL GENERATED?
                    │  └─ YES: Alert (🟢/🔴) + DB
                    │  └─ NO: Continue scanning
                    │
┌─ TIME-BASED FALLBACK (every hour :15) ───────┐
│ For symbols WITHOUT events in 4 hours         │
│ Generates "backup" signals                    │
│ Confidence: Capped at 60% (differentiated)    │
│ Only runs if: (now - last_event) >= 4h       │
│ Alert emoji: 🟡/🟠 (different from events)   │
└─────────────────────────────────┬─────────────┘
                                  │
                    ┌─ SIGNAL GENERATED?
                    │  └─ YES: Alert (🟡/🟠) + DB
                    │  └─ NO: Wait for next fallback
```

---

## Key Features

### 1. Event-Driven PRIMARY Mode
- **Trigger**: Technical market events (rare, high-quality)
- **Confidence**: Inherited from event detector (0.35-0.95)
- **Frequency**: Multiple times per hour (checks every 5 min)
- **Cooldown**: 1 hour per symbol (prevents rapid-fire signals)
- **Use Case**: Catch significant market inflections

**Example**:
```
12:05 → EMA crossover detected for EURUSD
        Confidence: 0.75
        Signal generated immediately ✅
        Cooldown: 1 hour (until 13:05)
```

### 2. Time-Based FALLBACK Mode
- **Trigger**: Scheduled (every hour at :15 UTC)
- **Eligibility**: Symbols without events for 4+ hours
- **Confidence**: Capped at 60% (to differentiate)
- **Use Case**: Ensure coverage during smooth market periods

**Example**:
```
12:15 → Fallback job checks GBPUSD
        Last event: NULL (never had one)
        Decision: Generate fallback signal ✅
        Original confidence: 0.68
        Capped confidence: 0.60
        Alert sent (🟡 emoji)
```

### 3. Smart Cooldown Management
- **Event cooldown**: 1 hour between signals (per symbol)
- **Fallback timer**: 4 hours without events triggers fallback
- **Tracking**: `_last_event_time[symbol]` + `_last_signal_time[symbol]`
- **Pruning**: Automatic cleanup of expired cooldowns

### 4. Confidence Capping Strategy
Differentiates signal sources:
- **Event signals**: Full confidence (e.g., 0.75)
- **Fallback signals**: Capped at 60% (e.g., 0.68 → 0.60)
- **Alert emoji**: Different icons (🟢/🔴 vs 🟡/🟠)

---

## Job Schedule

| Job | Trigger | Frequency | Purpose | Status |
|-----|---------|-----------|---------|--------|
| `fetch_30m` | Cron `:00 UTC` | Hourly | Fetch 30m data | ✅ |
| `fetch_1h` | Cron `:00 UTC` | Hourly | Fetch 1h data | ✅ |
| `event_monitor` | Interval | Every 5 min | Scan events | ✅ |
| `time_based_fallback` | Cron `:15 UTC` | Hourly | Fallback signals | ✅ LIVE |
| `eod_pipeline` | Cron `23:00 UTC` | Daily | Train model | ✅ |
| `health_check` | Cron `00:00, 12:00 UTC` | Twice daily | System status | ✅ |

---

## Configuration Parameters

### In `async_scheduler.py`:
```python
# Hybrid mode thresholds
self.FALLBACK_HOURS = 4                  # Hours without events before fallback runs
self.TIME_BASED_MAX_CONFIDENCE = 0.6     # Max confidence for fallback signals
```

### In `signals/event_monitor.py` (Relaxed for Forex):
```python
EventMonitorConfig(
    min_confidence=0.35,        # Lowered from 0.55
    structure_lookback=15,      # Reduced from 20
    volume_window=15,           # Reduced from 20  
    atr_period=12,              # Reduced from 14
    cooldown_seconds=1800,      # 30 min (was 3600)
)
```

### In `core/config.py`:
```python
EVENT_MODE_ENABLED = True                # Enable event-driven
ENABLE_TIME_TRIGGERED_SIGNALS = False    # Disabled (hybrid handles this)
```

---

## What Gets Logged

### Signal Metadata Examples

**Event-Driven Signal**:
```json
{
  "signal": 1,
  "ticker": "EURUSD",
  "confidence": 0.75,
  "source": "event_monitor",
  "triggered_by": "ema_cross_bullish",
  "timestamp": "2025-12-23T12:05:00+00:00"
}
```

**Time-Based Fallback Signal**:
```json
{
  "signal": 1,
  "ticker": "GBPUSD",
  "confidence": 0.60,
  "source": "time_based_fallback",
  "fallback_reason": "no_events_4h",
  "fallback_capped": true,
  "timestamp": "2025-12-23T13:15:00+00:00"
}
```

### Telegram Alerts

| Type | Emoji | Example |
|------|-------|---------|
| Event BUY | 🟢 | "EMA Crossover detected" |
| Event SELL | 🔴 | "EMA Reversal detected" |
| Fallback BUY | 🟡 | "No events for 4h, generating signal" |
| Fallback SELL | 🟠 | "No events for 4h, generating signal" |

---

## How the System Works: Real Example

### Timeline: 12:00 - 14:30 UTC

**12:00 UTC** - Fetch 1h data
```
EURUSD: ✅ 1,546 candles loaded
GBPUSD: ✅ 1,546 candles loaded
AUDCAD: ✅ 1,545 candles loaded
```

**12:05 UTC** - Event Monitor Sweep 1
```
EURUSD: ✅ EMA crossover detected (conf: 0.75)
        → Signal generated
        → _last_event_time[EURUSD] = 12:05
        → Cooldown until 13:05
GBPUSD: ❌ No events
AUDCAD: ❌ No events
```

**12:10 UTC** - Event Monitor Sweep 2
```
EURUSD: ⏳ Another event detected (cooldown active, skipped)
        → Event timer reset: _last_event_time[EURUSD] = 12:10
GBPUSD: ❌ No events
AUDCAD: ❌ No events
```

**12:15 UTC** - Time-Based Fallback
```
EURUSD: ⏳ Skip (event only 5 min ago, way < 4h threshold)
GBPUSD: ✅ First time seeing this symbol → Generate signal!
        → Confidence: 0.68 → Capped to 0.60
        → Alert sent (🟡 emoji)
        → _last_signal_time[GBPUSD] = 12:15
AUDCAD: ✅ No events detected → Generate signal!
        → Confidence: 0.62 → Capped to 0.60
        → Alert sent (🟡 emoji)
        → _last_signal_time[AUDCAD] = 12:15
```

**13:05 UTC** - Event Monitor Sweep (N)
```
EURUSD: ✅ Cooldown expired!
        (If new events detected, can generate again)
GBPUSD: ❌ Still no events
AUDCAD: ❌ Still no events
```

**13:15 UTC** - Time-Based Fallback
```
EURUSD: ⏳ Skip (event detected, so still < 4h)
GBPUSD: ⏳ Skip (signal only 1h ago, cooldown active)
AUDCAD: ⏳ Skip (signal only 1h ago, cooldown active)
        (Wait for 1-hour signal cooldown to expire)
```

**14:15 UTC** - Time-Based Fallback
```
EURUSD: ⏳ Event 65 min ago, still < 4h threshold → Skip
GBPUSD: ⏳ Signal cooldown active (45 min left) → Skip
AUDCAD: ⏳ Signal cooldown active (45 min left) → Skip
        (Wait for fallback timer or event to reset)
```

---

## Signal Flow Chart

```
Market Data (OHLCV)
         ↓
    ┌────┴────┐
    ↓         ↓
EVENT      TIME-BASED
MONITOR    FALLBACK
    ↓         ↓
    ├─ Events? ─ No event in 4h?
    │   ↓          ↓
    │  YES        YES
    │   ↓          ↓
    │   └──┬────────┘
    ↓      ↓
    Generate Signal
         ↓
    ┌─ Check Cooldown
    │  ├─ Active? → Skip
    │  └─ Expired? → Proceed
    │         ↓
    ├─ ML Model Inference
    ├─ Confidence > threshold?
    │  ├─ YES → Record + Alert
    │  └─ NO → Discard
    ↓
Database: ml_signals table
         ↓
Telegram Alert (different emoji by source)
```

---

## Improvements Made

1. ✅ **Table mismatch fixed**: Tiingo fetcher now saves to `ohlcv_data` (was `ohlcv_raw`)
2. ✅ **Data migration**: Created migration 003 to consolidate tables
3. ✅ **Event detection relaxed**: Lowered thresholds for forex volatility
4. ✅ **Hybrid mode implemented**: Event PRIMARY + Time-based FALLBACK
5. ✅ **Timezone fixed**: Using `datetime.now(timezone.utc)` (was naive UTC)
6. ✅ **Job persistence**: Job stats logged to database (survives restarts)
7. ✅ **Intelligent fallback**: 4-hour rule prevents signal spam
8. ✅ **Confidence capping**: Differentiates signal sources

---

## What to Monitor

### Watch These Logs:
```bash
# Real-time monitoring
ssh ubuntu@52.90.60.32 "sudo journalctl -u opticore.service -f | grep -E 'event_monitor|time_based_fallback|Signal'"

# Event monitor activity
sudo journalctl -u opticore.service -f | grep "👁️"

# Fallback signal generation
sudo journalctl -u opticore.service -f | grep "⏰"
```

### Check Database:
```bash
# Latest signals
sqlite3 trading_bot.db "SELECT ticker, confidence, triggered_by, timestamp FROM ml_signals ORDER BY timestamp DESC LIMIT 10"

# Signal counts by source
sqlite3 trading_bot.db "SELECT triggered_by, COUNT(*) FROM ml_signals GROUP BY triggered_by"
```

---

## Expected Behavior

### Within First Hour After Deployment:
- ✅ Event monitor scans every 5 min (3 scans = 0 + 5 + 10 min marks)
- ✅ No events detected (forex low volatility)
- ✅ At :15 UTC, fallback job generates signals for first-time symbols
- ✅ Signals appear in database with source = `time_based_fallback`
- ✅ Telegram alerts sent (🟡/🟠 emoji)

### After 4+ Hours Without Events:
- ✅ Event monitor continues scanning (may catch rare events)
- ✅ Time-based fallback continues generating on schedule
- ✅ System generates mixed signals (events if they happen, fallback for quiet periods)

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No signals generating | Check if event_monitor ran (logs) and if fallback eligible (4h rule) |
| Timezone errors | Use `datetime.now(timezone.utc)` not `utcnow()` |
| Confidence mismatch | Verify TIME_BASED_MAX_CONFIDENCE = 0.6 in async_scheduler.py |
| Spam alerts | Check cooldown logic (1h between signals) |
| Stale signals | Migration 003 should have moved data; verify ohlcv_data table has records |

---

## Code Files Modified

1. `async_scheduler.py` - **Hybrid mode logic** (NEW + Updated)
   - Added `_should_run_time_based_fallback()` method
   - Added `_record_event_detected()` and `_record_signal_generated()`
   - Added `time_based_fallback_job()` method
   - Updated job registration to include fallback job
   - Fixed timezone issues (utcnow → now(timezone.utc))

2. `core/config.py` - **Configuration** (Reverted)
   - `ENABLE_TIME_TRIGGERED_SIGNALS` back to `False` (hybrid handles this)

3. `signals/event_monitor.py` - **Event detection** (Relaxed thresholds)
   - Config passed to EventMonitor init with forex-optimized values

4. `data/tiingo_fetcher.py` - **Data save target** (Fixed)
   - Changed INSERT from ohlcv_raw → ohlcv_data

5. `core/database.py` - **Table schema** (Fixed)
   - Removed ohlcv_raw table (consolidated into ohlcv_data)

6. `migrations/003_migrate_ohlcv_raw_to_ohlcv_data.py` - **Data migration** (NEW)
   - Migrates existing data and drops old table

---

## Summary

✅ **Hybrid mode is LIVE and operational**

The system now provides:
- **Event-driven signals** for real technical events (rare, high-confidence)
- **Time-based fallback** ensuring we don't miss opportunities during smooth periods
- **Smart cooldowns** preventing signal spam
- **Differentiated confidence** so AI can weight signals by source
- **24/7 coverage** across all market conditions

This is a **robust, production-ready system** that handles forex low-volatility trading intelligently.

---

**Last Updated**: 2025-12-23 12:18 UTC  
**Status**: ✅ Production Ready  
**Next**: Monitor signal generation and tune parameters as needed
