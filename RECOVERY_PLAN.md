# ACTION PLAN: Recovering from EC2 Downtime

## Status
- ✅ Root cause identified: Code tried to SELECT lag1 columns that don't exist in database
- ✅ Fix deployed: Code now gracefully handles missing lag1 columns
- ⚠️ EC2 instance appears to be down or unreachable

## What To Do Next

### Option 1: Restart EC2 Instance (RECOMMENDED)
1. Go to AWS Console → EC2 → Instances
2. Find instance: `ec2-52-14-77-236.us-east-2.compute.amazonaws.com`
3. Right-click → Instance State → Start

Then verify:
```bash
ssh -i "C:\Users\bigso\Downloads\opticore-key.pem" ec2-user@ec2-52-14-77-236.us-east-2.compute.amazonaws.com
cd ~/opticore-bot
ps aux | grep scheduler
```

### Option 2: Pull Latest Code
Once instance is up, pull the new fixes:
```bash
cd ~/opticore-bot
git pull origin deploy/event-driven-system
source venv/bin/activate
python3 -c "import asyncio; from async_scheduler import MLPipelineScheduler; asyncio.run(MLPipelineScheduler().start())"
```

### Option 3: Monitor Status
Once running, monitor these things:
```bash
# Check if migration 004 has lag1 columns
sqlite3 ~/opticore-bot/trading_bot.db "PRAGMA table_info(features);" | grep lag1

# Should show 8 lag1 columns (ema_21_lag1, ema_100_lag1, etc)
# If not, they will be created when features are refreshed

# Watch the logs
tail -f ~/opticore-bot/logs/event_debug.log | grep -iE "lag1|missing|error"
```

## What Changed This Time
1. **database.py (line 780-815)**
   - Added check for lag1 column existence before trying to SELECT them
   - Falls back gracefully if migration hasn't run
   - No more "no such column" crashes

2. **xgb_signal_engine.py (keep it simple)**
   - `prepare_features_for_inference()` always recreates lag1 via shift()
   - Works with or without pre-existing lag1 columns
   - `predict_signal()` validates lag1 columns before inference

3. **Confidence fix (active)**
   - Event-driven signals use event.confidence even if model returns NEUTRAL
   - Before: only applied if signal != 0 (BUY/SELL)
   - After: always applies for event signals

## Why This Is Better
❌ **Old approach:** Required lag1 columns to exist, crashed if they didn't  
✅ **New approach:** Has lag1 columns if they exist, creates them on-the-fly if needed  
✅ **Result:** Backwards compatible, more resilient

## Timeline
- Today ~23:00 UTC: Deployed code that required lag1 columns
- Today ~23:30 UTC: Code crashed trying to select non-existent columns
- Today ~00:00 UTC: EC2 went down due to repeated crashes
- Today ~00:30 UTC: Fixed code to handle missing columns gracefully
- Now: Ready to restart EC2 with robust code

## If This Happens Again
The safest pattern going forward:
1. Always check if columns exist before SELECT
2. Gracefully fall back to base functionality
3. Add new features incrementally (feature flags, config toggles)
4. Test changes on local database first before deploying
