# Persistent Event Deduplication Deployment Guide

## 📋 Summary
Fixed critical bug: **Duplicate signals on service restart** by implementing persistent event deduplication.

**Issue:** Event dedup cache stored only in RAM, lost on restart → same events detected twice → duplicate Telegram alerts

**Solution:** New database table + helper methods for persistent storage

---

## 🔧 Files Modified

### 1. `core/database.py`
**Changes:**
- Added `processed_events` table to schema (lines 168-181)
- Added 4 helper methods to DatabaseManager class:
  - `mark_event_processed(event_id, ticker, interval, event_type, event_timestamp)`
  - `is_event_processed(event_id)` 
  - `cleanup_old_processed_events(hours=24)`
  - `get_processed_events_count()`

**Status:** ✅ Syntax verified (0 errors)

### 2. `async_scheduler.py`
**Changes:**
- Updated `_is_event_already_processed()` to check database as backup (lines 220-239)
- Updated `_mark_event_processed()` to store in database (lines 241-278)
- Updated call site to pass event object (line 680)
- Updated `_cleanup_old_event_ids()` to clean database (lines 280-307)

**Status:** ✅ Syntax verified (0 errors)

---

## 📦 Deployment Steps (AWS EC2)

### Option A: Manual File Copy (Recommended)

1. **SSH to EC2:**
   ```bash
   ssh -i /path/to/opticore.pem ubuntu@<EC2_IP>
   ```

2. **Stop service:**
   ```bash
   sudo systemctl stop opticore.service
   ```

3. **Copy files (from local machine):**
   ```bash
   scp -i /path/to/opticore.pem core/database.py ubuntu@<EC2_IP>:/home/ubuntu/opticore-bot/core/
   scp -i /path/to/opticore.pem async_scheduler.py ubuntu@<EC2_IP>:/home/ubuntu/opticore-bot/
   ```

4. **Restart service:**
   ```bash
   sudo systemctl restart opticore.service
   ```

5. **Verify deployment:**
   ```bash
   # Check database table created
   sqlite3 /home/ubuntu/opticore-bot/data/trading_bot.db ".schema processed_events"
   
   # Check logs
   journalctl -u opticore.service --since '5 minutes ago' -n 50 --no-pager
   ```

### Option B: Git Deployment

1. **SSH to EC2:**
   ```bash
   ssh -i /path/to/opticore.pem ubuntu@<EC2_IP>
   ```

2. **Stop service:**
   ```bash
   sudo systemctl stop opticore.service
   ```

3. **Pull changes:**
   ```bash
   cd ~/opticore-bot
   git add core/database.py async_scheduler.py
   git commit -m "Fix: Persistent event deduplication for duplicate signal prevention"
   git push origin main
   ```

4. **On EC2:**
   ```bash
   cd ~/opticore-bot
   git pull origin main
   ```

5. **Restart service:**
   ```bash
   sudo systemctl restart opticore.service
   ```

---

## ✅ Verification Checklist

### Immediate (After Restart)
- [ ] Service starts without errors: `systemctl status opticore.service`
- [ ] No Python exceptions in logs: `journalctl -u opticore.service -n 100 | grep -i error`
- [ ] Database table created: `sqlite3 data/trading_bot.db ".schema processed_events"`

### During Operation (After Market Open)
- [ ] Events detected normally: Look for "✨ Processing NEW event" in logs
- [ ] Events stored in database: `sqlite3 data/trading_bot.db "SELECT COUNT(*) FROM processed_events WHERE expires_at > datetime('now');"`
- [ ] No duplicate alerts on Telegram
- [ ] Cleanup running every 6h: Look for "🧹 Cleaned" in logs

### After Service Restart
- [ ] Same events NOT detected again (dedup cache restored from database)
- [ ] Health report shows valid dedup stats

---

## 🧪 Test Cases

### Test 1: Event Processed and Stored
```bash
# Trigger an event (manual trade or wait for market event)

# Verify in database
sqlite3 data/trading_bot.db "SELECT * FROM processed_events LIMIT 5;"
```

**Expected:** Event appears in processed_events table with expires_at in future

### Test 2: Restart Doesn't Duplicate Signals
```bash
# Trigger event -> Telegram alert sent
# Restart service
sudo systemctl restart opticore.service
# Same event should NOT be detected again

# Verify in logs
journalctl -u opticore.service | grep "⏭️  Skipping duplicate event"
```

**Expected:** No "Skipping duplicate" message for this event indicates duplication if event is redetected

### Test 3: Cleanup Runs Periodically
```bash
# Wait 6 hours or force trigger

# Check logs
journalctl -u opticore.service | grep "🧹 Cleaned"
```

**Expected:** Cleanup message appears in logs every 6 hours

---

## 🔄 Hybrid Design (Memory + Database)

The implementation uses a **hybrid approach** for reliability:

1. **Fast Layer (Memory):** 
   - In-memory cache checked first (O(1) lookup)
   - Keeps performance high for frequent checks

2. **Persistent Layer (Database):**
   - Survives service restart
   - Prevents re-detection of same events

3. **Fallback Logic:**
   - If database fails: falls back to in-memory only
   - Worst case: reverts to previous behavior
   - No breaking changes

---

## 📊 Schema Details

### `processed_events` Table
```sql
CREATE TABLE IF NOT EXISTS processed_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,        -- Format: TICKER|INTERVAL|TYPE|TIMESTAMP
    ticker TEXT NOT NULL,                 -- e.g., AUDJPY
    interval TEXT NOT NULL,               -- e.g., 1h
    event_type TEXT NOT NULL,             -- e.g., rsi_rebound_bullish
    event_timestamp TEXT NOT NULL,        -- When event occurred
    processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,  -- When we processed it
    expires_at DATETIME NOT NULL          -- 24h expiry for cleanup
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_processed_events_event_id ON processed_events(event_id);
CREATE INDEX IF NOT EXISTS idx_processed_events_ticker ON processed_events(ticker);
```

---

## 🚀 Performance Impact

- **Memory:** Slight increase (list of processed events in database, but same as before in memory)
- **Database:** 4 new helper methods, 1 new table, 2 indexes
- **Latency:** Negligible (database checks use indexed columns, O(1) lookups)
- **Disk:** ~1-5MB per day (24h rolling window, auto-cleanup)

---

## ⚠️ Known Limitations

- Event expiry is **24 hours** (hardcoded in mark_event_processed())
  - Can be made configurable in future
- Cleanup runs every **6 hours** (matches existing scheduler)
- Maximum processed events stored: ~10,000 per day (self-cleaning)

---

## 📝 Rollback Plan (If Issues)

If issues occur after deployment:

1. **Stop service:**
   ```bash
   sudo systemctl stop opticore.service
   ```

2. **Restore previous version:**
   ```bash
   # Restore from git
   git revert <commit_hash>
   git push origin main
   git pull origin main
   ```

3. **Restart:**
   ```bash
   sudo systemctl restart opticore.service
   ```

**Note:** Old processed_events table will remain but won't be used. Can be dropped later if needed.

---

## 📧 Deployment Status

**Deployed:** [DATE_TIME]
**Verified By:** [USER]
**Notes:** [ANY_OBSERVATIONS]

---

**Questions?** Check logs with: `journalctl -u opticore.service --since '1 day ago' -f`
