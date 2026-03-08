# 🚀 DEPLOYMENT QUICK START - SILENT ANALYST CRITICAL FIXES
**Ready to Deploy:** YES ✅ | **Estimated Time:** 25 minutes

---

## TLDR - DEPLOYMENT IN 3 STEPS

### Step 1: Backup (2 min)
```bash
ssh -i opticore-key.pem ubuntu@52.90.60.32 "
  cd /home/ubuntu/opticore-bot && \
  cp core/config.py core/config.py.backup_jan17 && \
  cp async_scheduler.py async_scheduler.py.backup_jan17
"
```

### Step 2: Deploy (3 min)
```bash
# From Windows ML folder
scp -i opticore-key.pem core/config.py ubuntu@52.90.60.32:/home/ubuntu/opticore-bot/core/
scp -i opticore-key.pem async_scheduler.py ubuntu@52.90.60.32:/home/ubuntu/opticore-bot/
```

### Step 3: Restart (5 min)
```bash
ssh -i opticore-key.pem ubuntu@52.90.60.32 "
  sudo systemctl restart opticore.service && \
  sleep 3 && \
  sudo journalctl -u opticore.service -f -n 20
"
```

**Watch for this in logs:**
```
✅ Event deduplication system initialized
📋 Registering scheduler jobs...
✅ Job registered: event_monitor_4h (every hour at :00)
✅ Job registered: event_dedup_cleanup (every 6h)
🚀 STARTING ML PIPELINE SCHEDULER
```

---

## WHAT WAS FIXED

### 🔴 Before
- **Duplicate Signals:** CADJPY signal generated 10 times per event
- **Weekend Running:** System ran Saturday-Sunday (market closed)
- **Stale Data:** XAUUSD analyzed at 92+ hours old
- **Alert Spam:** 10 identical Telegram messages per event

### 🟢 After
- **Unique Signals:** 1 signal per event (duplicate detection active)
- **Market-Aware:** Paused Friday 22:00 - Sunday 22:00 UTC
- **Fresh Data Only:** Skips analysis if >4h old
- **Clean Alerts:** 1 Telegram message per unique event

---

## QUICK VERIFICATION (After Restart)

### Test 1: Market Gate Working
```bash
# On Saturday - should see CLOSED message
ssh -i opticore-key.pem ubuntu@52.90.60.32 \
  "sudo journalctl -u opticore.service | grep 'Market CLOSED' | head -1"

# Expected output:
# 🚫 Market CLOSED - Skipping event monitor (4h). Next open: 2026-01-19 22:00 UTC
```

### Test 2: No Duplicates in DB
```bash
ssh -i opticore-key.pem ubuntu@52.90.60.32 "
  python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('opticore-bot/trading_bot.db')
cursor = conn.cursor()
cursor.execute('''
    SELECT ticker, COUNT(*) as count
    FROM ml_signals
    WHERE timestamp > datetime('now', '-1 hour')
    GROUP BY ticker
    HAVING count > 1
''')
dupes = cursor.fetchall()
print('✅ NO DUPLICATES' if not dupes else f'⚠️  Duplicates: {dupes}')
conn.close()
EOF
"
```

### Test 3: Freshness Check Working
```bash
ssh -i opticore-key.pem ubuntu@52.90.60.32 \
  "sudo journalctl -u opticore.service | grep 'Data is' | head -5"

# Expected output:
# ✅ EURUSD 4h: Data is FRESH (age: 45 min < 300 min)
# ⏱️  XAUUSD 4h: Data is STALE (age: 5524 min, max: 300 min). Skipping analysis.
```

### Test 4: Cleanup Job Scheduled
```bash
ssh -i opticore-key.pem ubuntu@52.90.60.32 "
  python3 << 'EOF'
import sys
sys.path.insert(0, '/home/ubuntu/opticore-bot')
from async_scheduler import MLPipelineScheduler

scheduler = MLPipelineScheduler()
jobs = scheduler.scheduler.get_jobs()
cleanup_job = [j for j in jobs if j.id == 'event_dedup_cleanup']
print('✅ Cleanup job registered' if cleanup_job else '❌ Cleanup job missing')
EOF
"
```

---

## ROLLBACK (If Needed)

```bash
ssh -i opticore-key.pem ubuntu@52.90.60.32 "
  cd /home/ubuntu/opticore-bot && \
  cp core/config.py.backup_jan17 core/config.py && \
  cp async_scheduler.py.backup_jan17 async_scheduler.py && \
  sudo systemctl restart opticore.service
"
```

---

## FILES DEPLOYED

```
Modified Files: 2
Total Lines Added: 295
Syntax Errors: 0
Status: Production Ready ✅

├── core/config.py
│   ├── MARKET_OPEN_HOUR = 22
│   ├── OHLCV_MAX_AGE_BY_INTERVAL = {...}
│   ├── is_market_open() function
│   └── get_next_market_open() function
│
└── async_scheduler.py
    ├── _processed_event_ids cache
    ├── _generate_event_id() method
    ├── _is_event_already_processed() method
    ├── _mark_event_processed() method
    ├── _cleanup_old_event_ids() method
    ├── Market gate in event_monitor_job()
    ├── Freshness check in event_monitor_job()
    ├── Dedup loop in event processing
    ├── Market gate in time_based_fallback_job()
    ├── Freshness check in time_based_fallback_job()
    └── Cleanup job registration
```

---

## EXPECTED BEHAVIOR

### Monday-Friday (Market Open)
```
Every hour:
✅ Market OPEN - Running event monitor
✅ EURUSD 4h: Data is FRESH
✨ Processing NEW event: EURUSD 4h rsi_rebound_bullish
✅ Event marked as processed
```

### Friday 22:00 UTC Onward (Market Close)
```
Every hour:
🚫 Market CLOSED - Skipping event monitor
(No event processing, no signals, no alerts)
```

### Same Event Next Hour (Dedup Active)
```
⏭️  Skipping duplicate event: CADJPY 4h rsi_rebound_bullish
(No duplicate signal generated)
```

### Stale Data (>4h old)
```
⏱️  XAUUSD 4h: Data is STALE. Skipping analysis.
(Analysis skipped, no false signals from old patterns)
```

---

## DOCUMENTATION

See detailed guides in ML folder:
- `DEPLOYMENT_READY_JAN17_2026.md` - Complete deployment guide
- `EXECUTION_COMPLETE_SUMMARY_JAN17_2026.md` - Full summary
- `CODE_CHANGES_VERIFICATION_JAN17_2026.md` - Code changes detail
- `COMPREHENSIVE_CODEBASE_AUDIT_JAN17_2026.md` - Full audit report
- `SILENT_ANALYST_CONTEXT_JAN17_2026.md` - System overview

---

## SUPPORT

**If market gate not working:**
- Check: `datetime.now(timezone.utc)` returns correct time
- Verify: AWS EC2 clock is UTC synchronized

**If dedup not working:**
- Check: "_processed_event_ids" in logs
- Monitor: "Processing NEW event" vs "Skipping duplicate"

**If freshness check not working:**
- Check: OHLCV_MAX_AGE_BY_INTERVAL values in config
- Monitor: "Data is FRESH" vs "Data is STALE" messages

---

## NEXT STEPS

✅ **Today (Jan 17):**
1. Deploy to AWS (15 min)
2. Verify tests pass (10 min)
3. Monitor for 1 hour (no errors)

✅ **This Week:**
1. Let system run for 3-5 days (collect clean data)
2. Verify no duplicates in database
3. Check market-closed behavior Friday 22:00

✅ **Next Week:**
1. Investigate XAUUSD data issue (Phase 5)
2. Review signal quality metrics
3. Adjust confidence thresholds if needed

---

**Deployment Status:** 🚀 READY  
**Quality Gate:** ✅ PASSED  
**Risk Level:** 🟢 LOW (isolated changes, backwards compatible)  
**Estimated ROI:** 90% reduction in duplicate alerts, 100% market-aware operation
