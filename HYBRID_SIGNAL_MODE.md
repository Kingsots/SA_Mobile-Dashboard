# Hybrid Signal Generation System
## Event-Driven PRIMARY + Time-Based FALLBACK

**Status**: ✅ Live on EC2 (2025-12-23 12:10 UTC)

---

## Design Philosophy

The system uses a **dual-mode approach** to generate robust trading signals for forex markets with low volatility:

1. **Event-Driven PRIMARY** (every 5 min)
   - Detects technical market events (EMA crossovers, RSI reversals, structure breaks)
   - HIGH confidence (inherited from event detector confidence)
   - Immediate trigger = rare, high-quality signals
   - Prevents signal spam with 1-hour cooldown per symbol

2. **Time-Based FALLBACK** (every hour at :15 UTC)
   - Runs on schedule for symbols WITHOUT events in `FALLBACK_HOURS` (default: 4 hours)
   - CAPPED confidence at 0.6 (below event confidence) to differentiate signal types
   - Ensures we don't miss valid setups during prolonged quiet periods
   - Different emoji in alerts (🟡/🟠) vs event signals (🟢/🔴)

---

## How It Works

### Scenario 1: Event-Driven Path (Primary)
```
[Hour 0] Event Monitor detects EMA crossover for EURUSD
         → Event confidence: 0.75
         → Signal generated immediately
         → Records: _last_event_time[EURUSD] = now
         → Cooldown: 1 hour (prevents spam)
         
[Hour 1:15] Time-based fallback checks EURUSD
            → Only 75 min since last event
            → 75 < FALLBACK_HOURS (240 min)
            → Skips time-based generation (event active)
```

### Scenario 2: Time-Based Fallback Path
```
[Hour 0] Event Monitor scans GBPUSD
         → No events detected
         → Records: _last_event_time[GBPUSD] = None initially
         
[Hour 1] Event monitor continues (no new events)
[Hour 2] Event monitor continues (no new events)
[Hour 3] Event monitor continues (no new events)

[Hour 4:15] Time-based fallback checks GBPUSD
            → 4 hours since last event
            → 4 >= FALLBACK_HOURS (4 hours)
            → Generates time-based signal
            → Model confidence: 0.72
            → CAPPED to: 0.60 (TIME_BASED_MAX_CONFIDENCE)
            → Sends 🟡 alert (different emoji = different source)
            → Records: _last_signal_time[GBPUSD] = now
```

### Scenario 3: Smart Cooldown Management
```
[Hour 0:00] Event fires, signal generated → Cooldown starts
[Hour 0:05] Another event detected within 1h cooldown
            → Event itself logged but signal suppressed
            → Event timer STILL resets: _last_event_time = now
            
[Hour 1:15] Time-based fallback checks
            → Only 75 min since last event (even though 2 events)
            → Still too recent, skips
            
[Hour 5:15] Time-based fallback checks
            → 5 hours since last event
            → >= 4 hour threshold
            → Generates signal (fair chance for quiet symbols)
```

---

## Job Schedule

| Job | Trigger | Interval | Purpose |
|-----|---------|----------|---------|
| `fetch_30m` | Cron | Every :00 UTC | Fetch 30m OHLCV |
| `fetch_1h` | Cron | Every :00 UTC | Fetch 1h OHLCV + kickoff event monitor |
| `event_monitor` | Interval | Every 5 min | Scan for market events (primary) |
| `time_based_fallback` | Cron | Every :15 UTC | Fallback signals for quiet symbols |
| `eod_pipeline` | Cron | 23:00 UTC | Features + model training |
| `health_check` | Cron | 00:00 & 12:00 UTC | System status report |

**Scheduling Strategy**:
- Event monitor: `+0:00, +0:05, +0:10, +0:15, +0:20, +0:25, ...` (constant watch)
- Time-based: `+0:15` (staggered 15 min after hour boundary, after fetch)
- Result: **Event detection happens 3x before fallback generates (if needed)**

---

## Configuration Parameters

Located in `async_scheduler.py` (`MLPipelineScheduler.__init__`):

```python
self.FALLBACK_HOURS = 4                          # Hours without events before fallback triggers
self.TIME_BASED_MAX_CONFIDENCE = 0.6             # Max confidence cap for fallback signals
```

Also in `core/config.py`:
```python
EVENT_MODE_ENABLED = True                        # Enable event-driven mode
ENABLE_TIME_TRIGGERED_SIGNALS = False            # Disable forced time-based (fallback handles this)
```

---

## Event Detection Settings (Relaxed for Forex)

From `signals.event_monitor.EventMonitorConfig`:

```python
min_confidence: 0.35       # Lower from 0.55 for forex sensitivity
structure_lookback: 15     # Reduced from 20 for faster detection
volume_window: 15          # Reduced from 20 for responsive volume
atr_period: 12             # Reduced from 14 for quicker volatility
cooldown_seconds: 1800     # 30 min between symbol events
```

**Why relaxed?** Forex (0.04% daily volatility) requires aggressive detection to find any events.
**RSI still needs** 5-point reversal from overbought/oversold (at ~82 RSI, only 3.92 points away on data).

---

## Signal Flow & Metadata

### Event-Driven Signal
```json
{
  "signal": 1,
  "ticker": "EURUSD",
  "confidence": 0.75,
  "source": "event_monitor",
  "trigger_type": "ema_cross_bullish",
  "triggered_by": "event_monitor",
  "timestamp": "2025-12-23T12:15:00+00:00"
}
```

### Time-Based Fallback Signal
```json
{
  "signal": 1,
  "ticker": "GBPUSD",
  "confidence": 0.60,          # Capped from original 0.72
  "source": "time_based_fallback",
  "fallback_reason": "no_events",
  "fallback_capped": true,     # Indicates confidence was reduced
  "hours_without_events": 4.25,
  "timestamp": "2025-12-23T13:15:00+00:00"
}
```

---

## Alert Differentiation

Telegram alerts use different emojis to distinguish signal sources:

| Signal Type | Emoji | Meaning |
|-------------|-------|---------|
| Event-Driven BUY | 🟢 | Technical event triggered (high confidence) |
| Event-Driven SELL | 🔴 | Technical event triggered (high confidence) |
| Fallback BUY | 🟡 | Scheduled check, no recent events (confidence capped) |
| Fallback SELL | 🟠 | Scheduled check, no recent events (confidence capped) |

---

## Monitoring & Debugging

### Check Current Event Status
```bash
ssh ubuntu@52.90.60.32 "sudo journalctl -u opticore.service -f | grep -E 'event_monitor|time_based_fallback'"
```

### Check Last Event Times Per Symbol
```python
# From running scheduler
scheduler._last_event_time  # Dict[symbol -> datetime]
scheduler._last_signal_time  # Dict[symbol -> datetime]
```

### Health Check Includes
- Total signals (24h): breakdown by event vs fallback
- Last event detection per symbol
- Cooldown status per symbol
- Time since last signal per symbol

---

## Potential Improvements

1. **Adaptive Fallback Hours**: Increase `FALLBACK_HOURS` if system is generating too many signals
2. **Symbol-Specific Thresholds**: Different sensitivity per asset class (forex vs commodities)
3. **Event Confidence Weighting**: Weight signals by event confidence magnitude
4. **Feedback Loop**: Adjust `TIME_BASED_MAX_CONFIDENCE` based on win rate
5. **Dynamic RSI Threshold**: Adapt RSI rebound detection based on market regime

---

## Key Insights

✅ **Why hybrid?**
- Pure event-driven: Miss opportunities on smooth trends (common in forex)
- Pure time-based: Generate signals on schedule regardless of market conditions
- Hybrid: Event-first (rare + high quality), fallback ensures coverage

✅ **Why confidence capping?**
- Differentiates signal sources in alerts
- Prevents overtrading on routine scheduled scans
- Preserves event signals as "true positives"
- AI can weight signals differently by source

✅ **Why cooldowns?**
- Event cooldown: Prevents rapid repeated signals on same event cluster
- Fallback only every 1-4h: Respects throttling on quiet symbols
- System avoids "alert fatigue" while staying responsive

---

## Testing

### To verify hybrid mode is working:

1. **Watch event monitor** (should fire rarely - only on technical events)
   ```bash
   journalctl -u opticore.service -f | grep "event_monitor"
   ```

2. **Wait for fallback job at :15 UTC**
   ```bash
   journalctl -u opticore.service -f | grep "time_based_fallback"
   ```

3. **Confirm signals are generated** (check health check output)
   ```bash
   python system_status.py
   ```

4. **Check metadata** (tells you signal source)
   ```bash
   sqlite3 trading_bot.db "SELECT signal, ticker, confidence, triggered_by, timestamp FROM ml_signals ORDER BY timestamp DESC LIMIT 10"
   ```

---

**Last Updated**: 2025-12-23 12:10 UTC  
**Branch**: deploy/event-driven-system  
**Status**: ✅ Production Live
