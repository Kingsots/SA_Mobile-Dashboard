# Hybrid Mode - Quick Reference

**Your new event-driven + time-based hybrid signal system**

---

## TL;DR

✅ **Event-Driven PRIMARY**: Scans market every 5 min for technical events  
✅ **Time-Based FALLBACK**: Generates signals every 4 hours if no events detected  
✅ **Smart Cooldowns**: 1 hour between signals (prevents spam)  
✅ **Confidence Capping**: Fallback signals capped at 60% (differentiated)  
✅ **Live on EC2**: Deployed Dec 23, 2025 12:18 UTC

---

## Signal Types

### 🟢 Event-Driven BUY
- Technical event detected (EMA cross, RSI reversal, breakout)
- Confidence: 0.35 - 0.95 (inherited from event)
- Urgency: **HIGH** (market is moving)
- Position: 100% normal size

### 🔴 Event-Driven SELL
- Same as above, bearish direction
- Urgency: **HIGH**
- Position: 100% normal size

### 🟡 Fallback BUY
- No events for 4 hours, scheduled scan triggered signal
- Confidence: Capped at 0.60
- Urgency: **MEDIUM** (routine check)
- Position: 70% normal size

### 🟠 Fallback SELL
- Same as above, bearish direction
- Urgency: **MEDIUM**
- Position: 70% normal size

---

## When Signals Generate

```
EVERY 5 MINUTES (Event Monitor)
├─ Load OHLCV data
├─ Scan for technical events
├─ If event detected:
│  ├─ Check if in cooldown (1h rule)
│  ├─ If clear → Generate signal (🟢/🔴)
│  └─ If cooled → Skip signal, reset timer
└─ No event? → Wait for next scan

EVERY HOUR AT :15 UTC (Time-Based Fallback)
├─ For each symbol:
│  ├─ When was last event detected?
│  ├─ If never or > 4 hours ago:
│  │  ├─ Generate signal (conf capped at 0.60)
│  │  ├─ Alert sent (🟡/🟠)
│  │  └─ Cooldown: 1 hour
│  └─ If event < 4h ago:
│     └─ Skip (event-driven active)
```

---

## Key Parameters

| Parameter | Value | Meaning |
|-----------|-------|---------|
| Event Monitor | Every 5 min | Frequency of market scans |
| Fallback Job | Every hour :15 | Time-based signal generation |
| Event Cooldown | 1 hour | Min time between signals (same symbol) |
| Fallback Timer | 4 hours | How long without events before fallback |
| Fallback Confidence Cap | 0.60 | Max confidence for scheduled signals |
| Event Min Confidence | 0.35 | Sensitivity to market events |

---

## How to Monitor

### Live Logs
```bash
# Watch event monitor activity
ssh ubuntu@52.90.60.32 "sudo journalctl -u opticore.service -f | grep '👁️'"

# Watch fallback signal generation
ssh ubuntu@52.90.60.32 "sudo journalctl -u opticore.service -f | grep '⏰'"

# Watch for errors
ssh ubuntu@52.90.60.32 "sudo journalctl -u opticore.service -f | grep '❌'"
```

### Check Latest Signals
```bash
# Database query
ssh ubuntu@52.90.60.32 "cd /home/ubuntu/opticore-bot && sqlite3 trading_bot.db \"SELECT ticker, confidence, triggered_by, timestamp FROM ml_signals ORDER BY timestamp DESC LIMIT 20\""
```

### Signal Count by Source
```bash
ssh ubuntu@52.90.60.32 "cd /home/ubuntu/opticore-bot && sqlite3 trading_bot.db \"SELECT triggered_by, COUNT(*) as count FROM ml_signals GROUP BY triggered_by\""
```

---

## Troubleshooting

| Symptom | Check This |
|---------|-----------|
| No signals at all | Are OHLCV tables populated? (`sqlite3 trading_bot.db "SELECT COUNT(*) FROM ohlcv_data"`) |
| No event signals | Check if market has volatility (forex low vol expected) |
| No fallback signals | Verify fallback job registered: `journalctl -u opticore.service | grep "time_based_fallback"` |
| Too many signals | Reduce `FALLBACK_HOURS` or increase cooldown period |
| Wrong emoji | Check `triggered_by` field in database (should be `event_monitor` or `time_based_fallback`) |

---

## Configuration Files

### `async_scheduler.py` (Hybrid Logic)
```python
self.FALLBACK_HOURS = 4                     # ← Adjust this to change fallback frequency
self.TIME_BASED_MAX_CONFIDENCE = 0.6        # ← Adjust to trust fallback more/less
```

### `signals/event_monitor.py` (Event Sensitivity)
```python
EventMonitorConfig(
    min_confidence=0.35,        # ← Lower = more events (was 0.55)
    structure_lookback=15,      # ← Lower = faster detection (was 20)
    ...
)
```

### `core/config.py` (Global Settings)
```python
EVENT_MODE_ENABLED = True                   # Leave True for hybrid
ENABLE_TIME_TRIGGERED_SIGNALS = False       # Leave False (hybrid handles this)
```

---

## Deployment Notes

### Last Deployed
- **Date**: December 23, 2025
- **Time**: 12:18 UTC
- **Branch**: deploy/event-driven-system
- **Status**: ✅ Running

### Key Changes in Deployment
1. Added `time_based_fallback_job()` method
2. Fixed timezone issues (`datetime.now(timezone.utc)`)
3. Implemented `_should_run_time_based_fallback()` logic
4. Registered fallback job in scheduler (every hour :15)
5. Added signal source tracking

### Files Modified
- `async_scheduler.py` (major update)
- `core/config.py` (reverted time-based to false)
- Other files: No changes to logic

---

## Expected Signal Frequency

### Calm Market (Typical Forex)
- Event signals: 0-2 per 24h (rare)
- Fallback signals: 6 per 24h (one every 4h)
- **Total**: 6-8 signals per day

### Active Market
- Event signals: 10-20 per 24h
- Fallback signals: 0-2 per 24h (skipped due to events)
- **Total**: 10-20 signals per day

### Emoji Distribution in Telegram
- 🟢/🔴: Event signals (high priority)
- 🟡/🟠: Fallback signals (routine checks)

---

## Confidence Interpretation

### Event Signals (0.35 - 0.95)
```
0.35-0.45 = Weak event (marginal setup)
0.45-0.60 = Moderate event (decent signal)
0.60-0.75 = Strong event (good confidence)
0.75-0.95 = Excellent event (high confidence)
```

### Fallback Signals (capped at 0.60)
```
0.35-0.45 = Weak setup (low confidence)
0.45-0.60 = Moderate setup (acceptable)
0.60 = Strong fallback (capped here)
```

**Rule of Thumb**: Event signals 0.75+ are higher priority than fallback signals 0.60

---

## Adjusting Behavior

### Want More Signals?
1. Reduce `FALLBACK_HOURS` from 4 to 2
2. Reduce `min_confidence` from 0.35 to 0.25
3. Increase `TIME_BASED_MAX_CONFIDENCE` to 0.70

### Want Fewer Signals?
1. Increase `FALLBACK_HOURS` from 4 to 8
2. Increase `min_confidence` from 0.35 to 0.45
3. Decrease `TIME_BASED_MAX_CONFIDENCE` to 0.50

### Want Higher Quality Events?
1. Increase `structure_lookback` from 15 to 25
2. Increase `min_confidence` from 0.35 to 0.50

---

## Telegram Alert Format

### Event Signal
```
🟢 **ML Signal Alert**
**Symbol:** EURUSD
**Signal:** LONG
**Confidence:** 75%
**Interval:** 1h
**Trigger:** event_monitor
**Time:** 2025-12-23T12:05:00
```

### Fallback Signal
```
🟡 **Time-Based Fallback Signal**
**Symbol:** GBPUSD
**Signal:** LONG
**Confidence:** 60% (capped for fallback)
**Reason:** No events detected for 4h
**Time:** 2025-12-23T12:15:00
```

---

## Database Queries

### Total Signals by Source
```sql
SELECT triggered_by, COUNT(*) as count 
FROM ml_signals 
GROUP BY triggered_by;
```

### Recent Event Signals
```sql
SELECT ticker, confidence, timestamp 
FROM ml_signals 
WHERE triggered_by = 'event_monitor' 
ORDER BY timestamp DESC 
LIMIT 10;
```

### Recent Fallback Signals
```sql
SELECT ticker, confidence, timestamp 
FROM ml_signals 
WHERE triggered_by = 'time_based_fallback' 
ORDER BY timestamp DESC 
LIMIT 10;
```

### Signal Frequency by Hour
```sql
SELECT strftime('%Y-%m-%d %H:00', timestamp) as hour, COUNT(*) as count 
FROM ml_signals 
GROUP BY hour 
ORDER BY hour DESC 
LIMIT 24;
```

---

## Status Commands

### Check Service Running
```bash
ssh ubuntu@52.90.60.32 "sudo systemctl status opticore.service"
```

### Check Jobs Registered
```bash
ssh ubuntu@52.90.60.32 "sudo journalctl -u opticore.service -n 50 | grep 'Job registered'"
```

### Check Last 10 Signals
```bash
ssh ubuntu@52.90.60.32 "cd /home/ubuntu/opticore-bot && sqlite3 trading_bot.db \"SELECT timestamp, ticker, confidence, triggered_by FROM ml_signals ORDER BY timestamp DESC LIMIT 10\""
```

### Restart Service
```bash
ssh ubuntu@52.90.60.32 "sudo systemctl restart opticore.service"
```

---

**Last Updated**: December 23, 2025 | 12:18 UTC  
**System Status**: ✅ Live and Operational  
**For issues**: Check logs with `journalctl -f` command
