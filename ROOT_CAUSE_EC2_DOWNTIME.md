# ROOT CAUSE ANALYSIS: Why EC2 Went Down

## What Happened
1. **We added code to select lag1 columns from database** - changes looked good
2. **The migration to add those columns to the table may not have run** - or ran partially
3. **When the code tried to SELECT columns that don't exist, SQLite threw an error**
4. **This crashed the entire load_features() function**
5. **Without features, signal generation failed, causing bot downtime**

## The Problem Code (database.py line 790)
```python
# BEFORE: This would crash if lag1 columns don't exist
feature_cols = [
    'timestamp', 'ticker', 'interval',
    'open', 'high', 'low', 'close', 'volume',
    'ema_21', 'ema_100', 'rsi_14',
    'obv', 'ad', 'vwap', 'vwap_slope',
    'volume_sma_20', 'volume_ratio',
    'ema_21_lag1', 'ema_100_lag1', 'rsi_14_lag1',  # ← CRASH if not in table
    'obv_lag1', 'ad_lag1', 'vwap_slope_lag1',
    'volume_sma_20_lag1', 'volume_ratio_lag1'
]
```

SQLite Error: `no such column: ema_21_lag1`

## The Fix (database.py line 780)
```python
# AFTER: Check if columns exist first
lag1_cols = []
try:
    check_query = "PRAGMA table_info(features)"
    cols_info = pd.read_sql_query(check_query, conn)
    existing_col_names = cols_info['name'].tolist()
    
    lag1_candidates = ['ema_21_lag1', 'ema_100_lag1', ...]
    lag1_cols = [col for col in lag1_candidates if col in existing_col_names]
except Exception as e:
    logging.warning(f"Could not check for lag1 columns: {e}")
    lag1_cols = []

# Only select lag1 columns if they actually exist
feature_cols = [ ... base cols ... ]
if lag1_cols:
    feature_cols.extend(lag1_cols)

# ✅ Works with OR without lag1 columns!
```

## Why This Matters
- **Before:** Code would crash on ANY database without lag1 columns (old DB, fresh migration, etc)
- **After:** Code gracefully falls back to base features if lag1 not available, creates lag1 during inference
- **Result:** Bot stays UP even if lag1 columns haven't been added yet

## What This Means for You
✅ **The good news:**
- Your bot can now run on databases with or without lag1 columns
- This prevents cascade failures from incomplete migrations
- Code is backwards compatible

⚠️ **What still needs to happen:**
- Migration 004_add_lag1_features.py needs to be run on EC2 database
- Once columns exist, bot will load them directly (faster than recreating via shift)
- If migration doesn't exist or fails, bot still works (just recreates lag1 during inference)

## Next Steps
1. **Verify EC2 is back up** - try SSH
2. **Check if migration 004 ran on EC2 database**
   ```sql
   PRAGMA table_info(features);
   -- Look for ema_21_lag1, ema_100_lag1, etc columns
   ```
3. **If migration didn't run, it will run automatically** next time features are refreshed
4. **Monitor logs for "Lag1 columns not available" warnings** - means columns weren't found, but that's OK

## The Confidence Fix (Still Active)
Also kept: Event-driven signals now use event.confidence (pattern reliability) even when model returns NEUTRAL signal.
- Before: Only applied event confidence if model predicted BUY or SELL
- After: Always applies event confidence for event-driven signals
