# 🚀 INFERENCE GATE DEPLOYMENT GUIDE

**Date:** Feb 17, 2026  
**Branch:** `deploy/event-driven-system`  
**Status:** Ready for EC2 deployment

---

## Step 1: SSH to EC2

```bash
ssh ubuntu@52.90.60.32
```

---

## Step 2: Run Deployment Script

```bash
cd ~/SilentAnalyst
bash scripts/deploy_inference_gate.sh
```

**What it does:**
- ✅ Pulls latest code from `deploy/event-driven-system` branch
- ✅ Creates backups of modified files
- ✅ Shows recent commits
- ⚠️ Prompts you to restart service manually

---

## Step 3: Restart Your Signal Generation Service

This depends on how you run the service. Choose one:

### Option A: Supervisor (if using supervisor)
```bash
sudo supervisorctl restart silent_analyst_signals
# or whatever your service is called in supervisor config
```

### Option B: systemd (if using systemd)
```bash
sudo systemctl restart silent_analyst_signals
```

### Option C: Manual (kill and restart)
```bash
pkill -f "python3.*signals"
sleep 2
nohup python3 signals/main.py > logs/signals.log 2>&1 &
```

---

## Step 4: Start Monitoring

In a new terminal (on EC2), start the diagnostic monitor:

```bash
ssh ubuntu@52.90.60.32
cd ~/SilentAnalyst

# Real-time monitoring with 5-second updates, 60-second summaries
python3 scripts/monitor_inference_gate.py --interval 5 --report-interval 60

# Or with JSON export
python3 scripts/monitor_inference_gate.py --interval 5 --report-interval 60 --export-json
```

**What you'll see:**
```
🔍 INFERENCE GATE DIAGNOSTIC MONITOR
================================================================================
📁 Log file: logs/signal_debug.log
⏱️  Update interval: 5s
📊 Report interval: 60s
🔎 Monitoring markers: [DEBUG], [NaN_TRAP], [INFERENCE_GATE]
================================================================================

⏸️  [14:23:45] [INFERENCE_GATE] EURUSD 1m: 2 rows available, need 110. Returning None — inference skipped.
⏸️  [14:23:46] [INFERENCE_GATE] Event 12345 marked processed — insufficient history for EURUSD, will not retrigger.
⏸️  [14:23:50] [INFERENCE_GATE] GBPUSD 5m: 8 rows available, need 110. Returning None — inference skipped.
```

---

## What Each Marker Means

| Marker | Example | Meaning |
|--------|---------|---------|
| **[INFERENCE_GATE]** | `[INFERENCE_GATE] EURUSD 1m: 2 rows available, need 110...` | ✅ Gate blocked inference due to insufficient rows |
| **[NaN_TRAP]** | `[NaN_TRAP] Lag1 features NaN - returning NEUTRAL` | ❌ Should NOT appear (gate prevents this) |
| **[DEBUG]** | `[DEBUG] Predicting with X shape: (1, 24)` | 🔧 Verbose feature engineering debug |

---

## Expected Behavior After Deployment

### ✅ EXPECTED PATTERNS
```log
[INFERENCE_GATE] Event 1001 marked processed — insufficient history for EURUSD, will not retrigger.
[INFERENCE_GATE] EURGBP 1m: 5 rows available, need 110. Returning None — inference skipped.
```

### ❌ PROBLEMATIC PATTERNS (Report if seen)
```log
[NaN_TRAP] Lag1 features NaN - returning NEUTRAL
```

If you see `[NaN_TRAP]` frequently:
- Gate is NOT working
- Check: Is xgb_signal_engine_ec2.py actually deployed?
- Check: Did service restart pick up changes?

---

## Monitoring Output Interpretation

### Sample Summary Report
```
📊 DIAGNOSTIC SUMMARY - 2026-02-17 14:25:00
========================================================================
Marker Counts:
  ✅ INFERENCE_GATE      :    47
  ✅ NaN_TRAP            :     0
  ✅ DEBUG               :   123

Inference Gate Rejections by Symbol:
  ⏸️  EURUSD        :  12 rejections
  ⏸️  GBPUSD        :   8 rejections
  ⏸️  EURGBP        :   6 rejections
  ⏸️  GBPJPY        :  21 rejections

✅ No NaN Trap warnings (gate is working!)
========================================================================
```

**Good signs:**
- ✅ INFERENCE_GATE count > 0 (gate is active)
- ✅ NaN_TRAP count = 0 (no lag1 NaN issues)
- ✅ Multiple symbols showing gate rejections

**Bad signs:**
- ❌ NaN_TRAP count > 0 (gate not working)
- ❌ INFERENCE_GATE count = 0 (gate not firing)

---

## Step 5: Verify Signal Distribution

After monitoring for a few hours, check signal distribution:

```bash
# SSH to EC2
cd ~/SilentAnalyst

# Check latest signals
python3 -c "
import sqlite3
conn = sqlite3.connect('data/trading_bot.db')
c = conn.cursor()

# Event-driven signals (should show SELL after fix)
c.execute('''
SELECT signal, COUNT(*) as count 
FROM ml_signals 
WHERE triggered_by = 'event_monitor' 
AND timestamp > datetime('now', '-4 hours')
GROUP BY signal
''')
print('Event-driven signals (last 4 hours):')
for signal, count in c.fetchall():
    signal_name = {0: 'NEUTRAL', 1: 'BUY', -1: 'SELL'}.get(signal, str(signal))
    print(f'  {signal_name}: {count}')

conn.close()
"
```

**Expected after fix:**
```
Event-driven signals (last 4 hours):
  SELL: 12
  BUY: 14
  NEUTRAL: 2
```

**Before fix (0% SELL bug):**
```
Event-driven signals (last 4 hours):
  SELL: 0
  BUY: 10
  NEUTRAL: 28
```

---

## Troubleshooting

### Problem: Monitor shows NaN_TRAP warnings after deployment

**Solution:**
1. Check that xgb_signal_engine_ec2.py was actually updated:
   ```bash
   grep "MIN_INFERENCE_ROWS = 110" ~/SilentAnalyst/signals/xgb_signal_engine_ec2.py
   ```
   Should show the line - if not, re-deploy

2. Verify service restarted with new code:
   ```bash
   ps aux | grep python3
   grep "signal_engine_ec2" /proc/$(pgrep -f "python3.*signals")/maps
   ```

3. Restart service again:
   ```bash
   sudo supervisorctl restart silent_analyst_signals
   # (or your restart command)
   sleep 5
   ```

### Problem: INFERENCE_GATE count = 0, no gate rejections appearing

**Possible causes:**
- Service restarted but didn't pick up changes
- Events aren't triggering (market hours, cooldown)
- All intervals have sufficient history

**Debug:**
```bash
# Check logs for errors
tail -f logs/signal_debug.log | head -50

# Check if service is using new code
strings /proc/$(pgrep -f "python3.*signals")/exe | grep MIN_INFERENCE_ROWS
```

### Problem: INFERENCE_GATE appears but NaN_TRAP also still seen

**This means:** Some code path is bypassing the gate. Verify all 3 changes are in place:

```bash
grep -A 2 "if len(df_latest) < self.MIN_INFERENCE_ROWS" signals/xgb_signal_engine_ec2.py
grep -A 2 "if result is None:" signals/xgb_signal_engine_ec2.py
```

---

## Files Deployed

### Code Changes
- **signals/xgb_signal_engine_ec2.py**
  - Line 70: `MIN_INFERENCE_ROWS = 110`
  - Lines 210-218: Gate check in `get_latest_features()`
  - Lines 520-548: Gate logging in `generate_signal()`

- **async_scheduler.py**
  - Lines 695-715: Event monitor gate handling in `event_monitor_job()`
  - Marks events as processed when gate rejects them
  - Only increments `triggered` counter for actual signals

### Monitoring Tools
- **scripts/monitor_inference_gate.py** - Real-time diagnostic monitor
- **scripts/deploy_inference_gate.sh** - Automated deployment script

---

## Next Steps After Successful Deployment

1. **Let it run for 1-2 hours** - Collect diagnostic data
2. **Run diagnostic summary** - Export JSON, review patterns
3. **Check Telegram alerts** - Should see SELL signals (shorts) being generated
4. **Verify signal ratios** - Should match model output (~52% SELL, 48% BUY)
5. **Check event monitor stats** - Log shows actual triggered count (not gate rejections)

---

## Rollback Plan

If anything goes wrong, rollback is easy:

```bash
cd ~/SilentAnalyst
git reset --hard 612f2d0
# Service will need restart to pick up old code
```

The commit `612f2d0` is the last checkpoint before these changes.

---

## Questions or Issues?

1. Check the monitoring output for diagnostic markers
2. Review logs: `tail -f logs/signal_debug.log`
3. Export diagnostic summary: `python3 scripts/monitor_inference_gate.py --export-json`
4. Check git status: `git status` and `git log -5 --oneline`

