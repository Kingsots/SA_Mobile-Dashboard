================================================================================
🎯 NARROWED ROOT CAUSE INVESTIGATION
Systematic Code Review to Locate SELL Signal Suppression
================================================================================

Generated: 2026-02-17
Investigation Phase: Code Review & Logic Trace
Status: Ready for Targeted Investigation


================================================================================
WHAT WE KNOW FOR CERTAIN
================================================================================

  ✅ XGBoost model: WORKING (generates 52% SELL in bypass test)
  ✅ Model.predict(): CORRECT (maps classes to signals correctly)
  ✅ Model.predict_proba(): CORRECT (output probabilities are valid)
  
  ❌ Event-driven signals in database: 0% SELL
  ❌ Gap: 52% of SELL signals lost between model → database storage
  
  Smoking Gun Evidence:
  ├─ Raw model: 52 SELL out of 100
  ├─ Database: 0 SELL out of 100
  └─ Lost signals: ALL 52 SELL predicted are NEUTRAL in database


================================================================================
CRITICAL CODE PATHS TO INVESTIGATE
================================================================================

Path 1: generate_signal() method in xgb_signal_engine_ec2.py
──────────────────────────────────────────────────────────────
Line 488:       df_features = self.get_latest_features(ticker, interval, lookback=30)
                └─> Returns 31 rows (should be enough for lag1 shift)

Line 505:       signal, confidence = self.predict_signal(df_features_prepared)
                └─> CRUCIAL: Model is called here
                └─> Should return 1 (BUY), -1 (SELL), or 0 (NEUTRAL)
                └─> For 100 signals, should return ~52 SELL

Line 548:       'signal': signal,
                └─> Signal stored in dictionary

Line 625+:      Database save occurs
                └─> But signal value arrives as 0 (NEUTRAL) instead of -1 (SELL)

QUESTION: Between line 505 and 625, is signal being modified anywhere?
ANSWER: Code review shows NO modifications between those lines


Path 2: predict_signal() method (lines 230-300)
────────────────────────────────────────────────
The only place that returns NEUTRAL (0) is:

Line 266-268:   if len(available_cols) < len(lag1_feature_cols):
                    logging.warning(f"Missing lag1 features: {missing} - returning NEUTRAL")
                    return 0, 0.0

Line 281-286:   if X.isna().any().any():
                    missing_vals = X.columns[X.isna().any()].tolist()
                    logging.warning(f"NaN values in lag1 features: {missing_vals} - returning NEUTRAL")
                    return 0, 0.0

HYPOTHESIS 1: Lag1 features are NaN or missing
──────────────────────────────────────────────
If prepare_features_for_inference() creates lag1 features like:
    df['ema_21_lag1'] = df['ema_21'].shift(1)

And df only has 2 rows (lookback=1 + 1):
    Row 0: lag1 value = NaN (shift out of bounds)
    Row 1: lag1 value = Row 0's value ✓

Then Row 1 (the one used) should have valid lag1.

But! If get_latest_features somehow returns ONLY 1 row despite lookback=30+1,
then ALL lag1 features would be NaN, causing predict_signal to return 0.

INVESTIGATION NEEDED:
    ├─ Does get_latest_features return enough rows?
    ├─ Is tail_count calculated correctly? (line 188)
    ├─ For event-driven signals specifically, are features being loaded?
    └─ Could _refresh_features_if_stale be skipping refresh for events?


Path 3: Alternative - Features are NOT being passed correctly
───────────────────────────────────────────────────────────────
What if df_features_prepared doesn't have the right structure when passed to inference?

Could there be encoding isues?
    ├─ Feature names mismatched?
    ├─ Feature order wrong?
    ├─ NaN values not caught by the check?

INVESTIGATION NEEDED:
    ├─ Add logging to see actual feature values being passed to predict_signal
    ├─ Check if df_features.iloc[-1] gives expected values
    └─ Verify lag1 feature column names match model's expectations


Path 4: Race condition or state bug
────────────────────────────────────────
Could there be an issue with:
    ├─ Model state between calls?
    ├─ Feature engine state?
    ├─ Database read/write race condition?

Unlikely but possible for event-driven signals if they're processed differently


================================================================================
MOST LIKELY ROOT CAUSE (Ranked by Probability)
================================================================================

RANK 1: Lag1 features are NaN in predict_signal (Probability: 60%)
────────────────────────────────────────────
Reason:
  ├─ This explains ALL SELL signals becoming NEUTRAL (as 0 is default)
  ├─ Matches the pattern in predict_signal logic
  ├─ prepare_features_for_inference creates lag1 with shift (line 221)
  └─ Would only affect event-driven if get_latest_features returns < 2 rows for events

Evidence:
  ├─ Comment at line 566 hints model might return NEUTRAL for events
  └─ No other code path explains the 52→0 conversion

Fix if true:
  ├─ Ensure get_latest_features returns > 1 row even for single event
  ├─ Or compute lag1 from raw OHLC instead of relying on lookback rows
  └─ Or use previous candle's lag1 if available


RANK 2: Event-driven signals use different code path (Probability: 25%)
─────────────────────────────────────────
Reason:
  ├─ Would explain why event signals are ALL NEUTRAL but time signals work
  ├─ User investigation didn't filter by trigger source (both types checked?)
  └─ Could be separate event handler

Evidence:
  └─ Comments mention "event signal" separately (but code looks unified)

Fix if true:
  ├─ Search for event handler that might override generate_signal
  ├─ Check async_scheduler.py for event processing
  └─ Find any method that calls save_signal without generate_signal


RANK 3: Feature snapshot doesn't include lag1 (Probability: 10%)
───────────────────────────────────────────
Reason:
  ├─ Snapshot spec (lines 520-550) doesn't include lag1 features
  ├─ But generate_signal uses df_features_prepared with lag1
  └─ So this shouldn't affect signal generation

Evidence:
  └─ Code path is clear - model gets prepared features, not snapshot

Fix if true:
  ├─ Add lag1 features to snapshot for transparency
  └─ Doesn't fix generation, only improves diagnostics


RANK 4: Model class/prediction mapping is wrong (Probability: 5%)
─────────────────────────────────
Reason:
  ├─ Bypass test said it worked, so unlikely
  ├─ But check_predict_alignment found mismatches
  └─ Could be signal label mapping issue

Evidence:
  ├─ reverse_label_map at line 279: {0: -1, 1: 1}
  └─ But bypass script uses same mapping with different result

Actually:
  └─ This doesn't explain the 0 (NEUTRAL) in database


================================================================================
TARGETED INVESTIGATION PLAN
================================================================================

STEP 1: Add detailed logging (15 minutes)
─────────────────────────────────────────
Add to predict_signal (before checking for NaN):
```python
logging.info(f"predict_signal: X.shape={X.shape}, columns={available_cols}")
logging.info(f"predict_signal: First row: {X.iloc[0].to_dict()}")
logging.info(f"predict_signal: NaN check result: {X.isna().any().any()}")
```

Add to generate_signal (after predict_signal call):
```python
logging.info(f"generate_signal event-driven: signal={signal}, confidence={confidence}")
logging.info(f"generate_signal: LAG1 features check: {[c for c in df_features_prepared.columns if 'lag1' in c]}")
```

STEP 2: Compare time-based vs event-driven (10 minutes)
──────────────────────────────────────────────────────
Run a test that generates:
  ├─ 10 time-based signals → Check for SELL percentage
  ├─ 10 event-driven signals → Check for SELL percentage
  └─ Compare: Time-based should show mixed results, event should show all NEUTRAL

If time-based shows SELL and event doesn't = different code path issue
If both show 0% SELL = problem is before event/time split

STEP 3: Extract raw features for event-driven signals (10 minutes)(
───────────────────────────────────────────────────────────
Query database: When an event-driven signal was generated, what features did it have?
  ├─ Does the feature_snapshot show indicators?
  ├─ If we reconstruct lag1 from older snapshot, would it work?
  └─ Can we load historical features for that timestamp?

STEP 4: Trace specific signal (5 minutes)
──────────────────────────────
Pick ONE event-driven SELL prediction that ended up NEUTRAL:
  ├─ Get its timestamp, ticker, interval
  ├─ Manually load features for that moment
  ├─ Call predict_signal with those exact features
  ├─ See if we get SELL or NEUTRAL
  └─ If NEUTRAL = problem is feature preparation
  └─ If SELL = problem is database save path


================================================================================
RECOMMENDED NEXT STEPS
================================================================================

IMMEDIATE (5 minutes):
  └─ Run comprehensive_feature_diagnostic.py to understand feature state

SHORT TERM (30 minutes):
  ├─ Add logging to predict_signal per STEP 1
  ├─ Re-run signal generation with logging enabled
  ├─ Check logs for where signals are becoming NEUTRAL

MEDIUM TERM (60 minutes):
  ├─ Implement STEP 2 comparison test
  ├─ Narrow down: Is it model, features, or event handling?
  └─ Based on results, proceed to targeted fix

================================================================================
DO NOT
================================================================================

  ❌ DON'T assume model is broken (it's not - verified)
  ❌ DON'T retrain (training data is fine - waste of time)
  ❌ DON'T change model architecture (not the issue)
  ✅ DO look at feature preparation for event signals
  ✅ DO add logging to trace execution flow
  ✅ DO create minimal reproduction test


================================================================================
ROOT CAUSE: MOST LIKELY
================================================================================

Based on all evidence, the most likely scenario is:

📍 LOCATION: prepare_features_for_inference() or get_latest_features()
📍 ISSUE: produces NaN lag1 features for event-driven signals
📍 RESULT: predict_signal() returns 0 (NEUTRAL) due to NaN check
📍 IMPACT: All 52 SELL signals default to NEUTRAL before being stored

Fix would be simple - ensure lag1 features are never NaN, or compute them safely.

================================================================================
