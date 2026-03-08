# STEP 2.1: CLEAN MODEL RETRAINING - COMPLETE

**Date:** January 6, 2026  
**Status:** ✅ READY FOR EXECUTION

---

## Summary

**Step 2.1** creates a comprehensive retraining script that:
- Loads clean data (5000 rows, EURUSD 1h)
- Uses ONLY 8 safe, lagged indicators (no price leakage)
- Performs walk-forward validation (6-fold, time-series)
- Trains final model on 80/20 split
- Saves model + detailed metadata

---

## Files Created

### 1. `models/retrain_clean.py` (280 lines)

**Purpose:** Retrain XGBoost with leak-proof features

**Key functions:**
- `load_clean_data()` - Load 5000 historical rows
- `prepare_features()` - Create lag1 features, target construction
- `walk_forward_validation()` - 6-fold time-series split validation
- `train_final_model()` - Train on 80/20 split
- `evaluate_model()` - Calculate metrics (ACC, PREC, REC, F1)
- `save_model_and_metadata()` - Save model + comprehensive metadata

**Features used (8 indicators, all lagged by 1 bar):**
```python
base_features = [
    'ema_21', 'ema_100', 'rsi_14',           # Trend
    'volume_sma_20', 'volume_ratio',         # Volume
    'obv', 'ad', 'vwap_slope'                # Accumulation
]

# Automatically converted to lag1 versions in script:
# ema_21_lag1, ema_100_lag1, rsi_14_lag1, etc.
```

**No price features:** ✅ Confirmed (open, high, low, close removed)

**Walk-forward validation:**
- 6 folds, chronological split
- Each fold trains on past, tests on future
- True out-of-sample validation
- Expected mean accuracy: 52-58%

**Final model:**
- Trained on 80% of data
- Tested on remaining 20%
- Saved with timestamp: `model_clean_YYYYMMDD_HHMMSS.pkl`
- Metadata saved: `model_clean_metadata_YYYYMMDD_HHMMSS.json`

---

### 2. `PHASE_2_3_DEPLOYMENT_GUIDE.md` (420 lines)

**Purpose:** Decision tree for deployment based on walk-forward accuracy

**Scenarios covered:**

| Accuracy | Decision | Action | ML Confidence |
|---|---|---|---|
| > 65% | 🔴 REJECT | Investigate leakage | N/A |
| 58-65% | ✅ DEPLOY | Immediate production | 60% |
| 52-58% | ✅ DEPLOY | Live with monitoring | 70% |
| 50-52% | ⚠️ TEST | Paper trade 30 days | 80% |
| < 50% | ❌ REJECT | Event-driven only | N/A |

**Detailed guidance for each scenario:**
- Why that accuracy range is good/bad
- Specific deployment steps
- Risk mitigation strategies
- Monitoring requirements
- Success criteria

---

### 3. `PHASE_2_QUICK_REFERENCE.txt` (200 lines)

**Purpose:** Quick lookup guide for execution

**Contents:**
- Execution command and expected runtime
- Decision tree visual
- Success criteria
- Red flags to watch
- Post-deployment monitoring
- Quick action reference table

---

## Execution Steps

### Step 1: Run the retraining script

```bash
cd c:\Users\bigso\Downloads\ML
python models/retrain_clean.py
```

**Expected runtime:** 3-5 minutes

**Expected output example:**
```
[HH:MM:SS] 🤖 CLEAN MODEL RETRAINING (No Price Leakage)
[HH:MM:SS] 📥 Loading features from database...
[HH:MM:SS]    ✅ Loaded 5000 rows
[HH:MM:SS] 🔧 Preparing clean features...
[HH:MM:SS]    ✅ Prepared 4500 samples
[HH:MM:SS]    ✅ Features: 8 (all lagged by 1 bar)
[HH:MM:SS]    ✅ Target distribution: 2250 ups, 2250 downs
[HH:MM:SS] 
[HH:MM:SS] 📊 WALK-FORWARD VALIDATION (6 folds)
[HH:MM:SS] ============================================================
[HH:MM:SS] Fold 1: Train   375, Test   375 → ACC 51.2% PREC 50.5% REC 45.3% F1 47.7%
[HH:MM:SS] Fold 2: Train   750, Test   375 → ACC 53.4% PREC 52.1% REC 48.2% F1 50.0%
[HH:MM:SS] Fold 3: Train  1125, Test   375 → ACC 54.1% PREC 53.8% REC 49.1% F1 51.3%
[HH:MM:SS] Fold 4: Train  1500, Test   375 → ACC 52.8% PREC 51.9% REC 47.8% F1 49.7%
[HH:MM:SS] Fold 5: Train  1875, Test   375 → ACC 55.9% PREC 54.1% REC 51.2% F1 52.6%
[HH:MM:SS] Fold 6: Train  2250, Test   375 → ACC 54.3% PREC 53.4% REC 50.2% F1 51.7%
[HH:MM:SS] ────────────────────────────────────────────────────────
[HH:MM:SS] Mean Accuracy: 54.2% ± 1.8%
[HH:MM:SS] ✅ VALID: Accuracy in realistic range (52-58% expected)
[HH:MM:SS]
[HH:MM:SS] 🎯 FINAL MODEL TRAINING (80/20 split)
[HH:MM:SS] ============================================================
[HH:MM:SS] Train set: 3600 samples
[HH:MM:SS] Test set:   900 samples
[HH:MM:SS]
[HH:MM:SS] 📈 FINAL MODEL METRICS
[HH:MM:SS] ============================================================
[HH:MM:SS] Accuracy:  54.56%
[HH:MM:SS] Precision: 53.21%
[HH:MM:SS] Recall:    48.92%
[HH:MM:SS] F1-Score:  50.95%
[HH:MM:SS]
[HH:MM:SS] 💾 SAVING MODEL AND METADATA
[HH:MM:SS] ============================================================
[HH:MM:SS] ✅ Model saved: models/model_clean_20260106_143022.pkl
[HH:MM:SS] ✅ Metadata saved: models/model_clean_metadata_20260106_143022.json
[HH:MM:SS]
[HH:MM:SS] ✅ RETRAINING COMPLETE
[HH:MM:SS] ============================================================
[HH:MM:SS]
[HH:MM:SS] Model Summary:
[HH:MM:SS]   • Walk-forward accuracy: 54.20% ± 1.80%
[HH:MM:SS]   • Test set accuracy: 54.56%
[HH:MM:SS]   • Features: 8 (all lagged by 1 bar)
[HH:MM:SS]   • No price leakage: ✅ Confirmed
[HH:MM:SS]
[HH:MM:SS] Decision:
[HH:MM:SS]   ✅ SLIGHT EDGE - Deploy cautiously, monitor
[HH:MM:SS]
[HH:MM:SS] Files saved:
[HH:MM:SS]   📦 models/model_clean_20260106_143022.pkl
[HH:MM:SS]   📝 models/model_clean_metadata_20260106_143022.json
```

### Step 2: Review the results

Look at walk-forward accuracy:
- If **58-65%**: ✅ Strong edge → Deploy immediately
- If **52-58%**: ✅ Slight edge → Deploy with monitoring
- If **50-52%**: ⚠️ Marginal → Paper trade 30 days
- If **< 50%**: ❌ No edge → Use event-driven only

### Step 3: Make deployment decision

Based on accuracy, follow the decision tree in `PHASE_2_3_DEPLOYMENT_GUIDE.md`

---

## Metadata Structure

The saved metadata file will contain:

```json
{
  "timestamp": "20260106_143022",
  "model_type": "XGBoost (Clean, No Leakage)",
  "accuracy": 0.5456,
  "precision": 0.5321,
  "recall": 0.4892,
  "f1": 0.5095,
  "walk_forward": {
    "mean_accuracy": 0.5420,
    "std_dev": 0.0180,
    "folds": [
      {"fold": 1, "train_size": 375, "test_size": 375, "accuracy": 0.512, ...},
      {"fold": 2, "train_size": 750, "test_size": 375, "accuracy": 0.534, ...},
      ...
    ]
  },
  "features": {
    "count": 8,
    "lagged_columns": ["ema_21_lag1", "ema_100_lag1", ...],
    "base_columns": ["ema_21", "ema_100", ...]
  },
  "config": {
    "n_estimators": 200,
    "max_depth": 7,
    "learning_rate": 0.05,
    ...
  },
  "note": "This model uses only lagged indicators (no price features)..."
}
```

---

## Quality Assurance Checklist

Before execution:
- ✅ features/engine.py has lagging code
- ✅ Database has lag1 columns
- ✅ Python has xgboost installed
- ✅ Script syntax verified

After execution:
- [ ] Output shows 6 walk-forward folds
- [ ] Accuracy between 50-60%
- [ ] No NaN or error messages
- [ ] Model file created
- [ ] Metadata file created
- [ ] Decision made (deploy/reject/test)

---

## Troubleshooting

| Issue | Solution |
|---|---|
| "lag1 columns not found" | Run: `python models/xgb_trainer.py` first to generate lag1 features |
| "accuracy > 65%" | Investigate features; run diagnostic tests again |
| "accuracy < 50%" | Model has no edge; use event-driven detection only |
| "Script takes > 10 min" | Database query might be slow; check SQLite index |
| "Memory error" | Reduce limit from 5000 to 2000 in script |

---

## Key Metrics to Monitor

### Walk-Forward Validation:
- **Mean accuracy:** Should be 52-58% (realistic)
- **Std dev:** Should be < 3% (stable across folds)
- **Individual folds:** 48-62% range acceptable

### Final Model:
- **Accuracy:** Should match walk-forward (±2%)
- **Precision:** How many predicted wins are actual wins
- **Recall:** How many actual wins are caught
- **F1:** Balanced view of precision + recall

---

## Integration with Production

### If deploying (accuracy ≥ 52%):

```bash
# 1. Copy new model
cp models/model_clean_YYYYMMDD_HHMMSS.pkl models/model_current.pkl

# 2. Update config
# In core/config.py:
# ML_SIGNAL_CONFIDENCE_MIN = 0.60 (or 0.70 if 52-58%)

# 3. Commit to git
git add models/model_current.pkl core/config.py
git commit -m "PHASE 2: Deploy clean model v2 with lag(1) features"

# 4. Deploy to EC2
scp models/model_current.pkl ubuntu@52.90.60.32:/home/ubuntu/opticore-bot/models/
scp core/config.py ubuntu@52.90.60.32:/home/ubuntu/opticore-bot/core/
ssh ubuntu@52.90.60.32 "systemctl restart opticore"

# 5. Monitor
# Check Telegram alerts start flowing again
# Track win rate after 30+ trades
```

---

## Expected Timeline

| Step | Time | Status |
|---|---|---|
| Script execution | 3-5 min | Ready |
| Result review | 2-5 min | Ready |
| Decision making | 1 min | Use decision tree |
| Deployment (if yes) | 5-10 min | Commands provided |
| Monitoring | 30+ days | Trade log required |

**Total to deployment:** ~15 minutes (if all good)

---

## Success Criteria

✅ **Success:**
- Walk-forward accuracy 52-58%
- Final model accuracy matches walk-forward (±2%)
- No NaN or errors in output
- Model saved successfully
- Ready for deployment

❌ **Failure:**
- Accuracy > 65% (suspicious)
- Accuracy < 50% (no edge)
- NaN/error in output
- Model fails to save
- Database issues

---

## Next Actions

1. **Execute:** `python models/retrain_clean.py`
2. **Wait:** 3-5 minutes for completion
3. **Check:** Walk-forward accuracy result
4. **Decide:** Follow decision tree in PHASE_2_3_DEPLOYMENT_GUIDE.md
5. **Deploy:** If ≥52%, proceed with deployment
6. **Monitor:** Track actual win rate for 30+ trades

---

## Ready?

Execute:
```bash
python models/retrain_clean.py
```

Then consult: `PHASE_2_3_DEPLOYMENT_GUIDE.md`

---

**Status: ✅ READY FOR EXECUTION**

Date: January 6, 2026  
Estimated completion: January 6, 2026 (today, in 5 minutes)
