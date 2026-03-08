# PHASE 2 & 3: RETRAIN AND DEPLOY DECISION GUIDE

**Date:** January 6, 2026  
**Status:** Ready for execution

---

## Phase 2: Clean Model Retraining

### Step 2.1 - Retrain Script Created ✅

**File:** `models/retrain_clean.py`

**What it does:**
1. Loads 5000 historical rows (EURUSD, 1h)
2. Uses ONLY 8 clean, lagged indicators (no prices)
3. Performs walk-forward validation (6 folds)
4. Trains final model on 80/20 split
5. Saves model and comprehensive metadata

**To execute:**
```bash
python models/retrain_clean.py
```

**Expected execution time:** 3-5 minutes

**Expected output:**
```
[HH:MM:SS] 📥 Loading features from database...
[HH:MM:SS]    ✅ Loaded 5000 rows
[HH:MM:SS] 🔧 Preparing clean features...
[HH:MM:SS]    ✅ Prepared 4500 samples (lag removed first row)
[HH:MM:SS] 📊 WALK-FORWARD VALIDATION (6 folds)
[HH:MM:SS] Fold 1: Train  375, Test  375 → ACC 51.2% PREC 50.5% REC 45.3% F1 47.7%
[HH:MM:SS] Fold 2: Train  750, Test  375 → ACC 53.4% PREC 52.1% REC 48.2% F1 50.0%
...
[HH:MM:SS] Mean Accuracy: 54.2% ± 2.8%
[HH:MM:SS] 🎯 FINAL MODEL TRAINING (80/20 split)
[HH:MM:SS] Accuracy:  54.56%
[HH:MM:SS] Precision: 53.21%
[HH:MM:SS] Recall:    48.92%
[HH:MM:SS] F1-Score:  50.95%
[HH:MM:SS] ✅ Model saved: models/model_clean_YYYYMMDD_HHMMSS.pkl
```

---

## Phase 3: Deployment Decision Tree

### Walk-Forward Accuracy Result:

```
Walk-Forward Accuracy
         ↓
    ┌────────────────────────────────────────────┐
    │                                            │
  > 65%              58-65%           52-58%    <50%
    ↓                  ↓                 ↓        ↓
 🔴 REJECT        ✅ STRONG        ✅ SLIGHT   ❌ NO EDGE
 (Recheck         EDGE             EDGE        (Reject,
  leakage!)       Deploy!          Deploy!      Rethink)
                                   (Monitor)
```

---

## Detailed Decision Criteria

### 🔴 **Accuracy > 65%: SUSPICIOUS**

**What it means:**
- Model achieved accuracy > 65% on walk-forward (future-proof test)
- This is unusually high for real trading data
- Indicates possible remaining leakage or overfitting

**Action:**
1. ❌ **DO NOT DEPLOY**
2. Re-run diagnostic leakage tests
3. Review feature engineering
4. Check for calendar effects, survivorship bias, or other artifacts
5. Go back to Step 1 and review feature selection

**Example:** If result is 72%, investigate whether lagging was actually applied correctly.

---

### ✅ **Accuracy 58-65%: STRONG EDGE**

**What it means:**
- Model found genuine predictive pattern
- Beating 50% baseline by 8-15% is excellent
- Statistically significant edge exists
- Confidence: HIGH

**Action:**
1. ✅ **APPROVE FOR DEPLOYMENT**
2. Copy model to production: `cp model_clean_YYYYMMDD_HHMMSS.pkl model_current.pkl`
3. Update confidence threshold: **60%** (conservative)
   ```python
   ML_SIGNAL_CONFIDENCE_MIN = 0.60  # in core/config.py
   ```
4. Deploy to EC2 immediately
5. Expected profitability: **HIGH**
6. Monitor for minimum 50 trades, expected 25-30 wins

**Trading approach:**
- Use event detection + ML confirmation
- Risk/reward: 1:1.5 (modest targets)
- Stop loss: ATR-based (already implemented)

---

### ✅ **Accuracy 52-58%: SLIGHT EDGE**

**What it means:**
- Model has detectable but modest edge
- Beating 50% baseline by 2-8% is significant
- Statistically measurable, but tight margin
- Confidence: MEDIUM

**Action:**
1. ✅ **APPROVE FOR DEPLOYMENT** (with caution)
2. Copy model to production: `cp model_clean_YYYYMMDD_HHMMSS.pkl model_current.pkl`
3. Update confidence threshold: **70%** (more conservative)
   ```python
   ML_SIGNAL_CONFIDENCE_MIN = 0.70  # in core/config.py
   ```
4. Set paper trading period: **30 trades minimum**
5. Deploy, but monitor closely
6. Expected profitability: **MODERATE**
7. Require win rate > 52% before scaling

**Trading approach:**
- Only trade high-conviction signals (70% + event detection)
- Tight stop losses, reasonable targets
- Log every trade for analysis
- Check after 20, 40, 60 trades whether maintaining 52%+ accuracy

**Success criteria:**
- After 30 trades: Actual win rate ≥ 52%
- If true: Scale to normal position sizes
- If false: Revert to event-driven only

---

### ⚠️ **Accuracy 50-52%: MARGINAL / NO STATISTICALLY SIGNIFICANT EDGE**

**What it means:**
- Model barely beats random guess (50%)
- Could be luck rather than true edge
- Risky to trade live
- Confidence: LOW

**Action:**
1. ⚠️ **CONDITIONAL DEPLOYMENT** (paper trade only)
2. Set up paper trading: **30 trades minimum**
3. Set confidence threshold: **80%** (very conservative)
   ```python
   ML_SIGNAL_CONFIDENCE_MIN = 0.80  # Require very high confidence
   ```
4. Collect data for 30 days or until 30 confirmed trades
5. Decision point: Does actual win rate exceed 52%?

**Paper trading checklist:**
```
After 30 Paper Trades:

Actual Win Rate > 52%?
  ├─ YES: ✅ Deploy with low position sizes
  └─ NO:  ❌ Abandon model, use event detection only
```

**Duration:** Paper trade for 30-60 days (not live capital)
**Monitoring:** Check win rate after 20, 30, 50 trades

---

### ❌ **Accuracy < 50%: NO EDGE**

**What it means:**
- Model performs WORSE than random guess
- No predictive power detected
- Model is losing trade
- Confidence: ZERO

**Action:**
1. ❌ **REJECT MODEL**
2. **DO NOT DEPLOY**
3. Return to event-driven detection only (already working)
4. Investigate:
   - Is lagging applied correctly?
   - Are features calculated correctly?
   - Try different indicators (RSI divergence, MACD, Stochastic)?
   - Try different timeframes (combine 30m + 4h)?
   - Try different lookback periods?

**Next steps:**
- Keep event detection running (it's profitable)
- Enhance feature set with more exotic indicators
- Consider multi-timeframe features
- Or accept that ML isn't needed for this market

---

## Quick Reference Table

| Walk-Forward Accuracy | Decision | ML Confidence | Action | Risk |
|---|---|---|---|---|
| > 65% | 🔴 REJECT | N/A | Investigate leakage | Medium |
| 58-65% | ✅ DEPLOY | 60% | Immediate production | Low |
| 52-58% | ✅ DEPLOY | 70% | Live with caution | Medium |
| 50-52% | ⚠️ PAPER | 80% | 30-trade test | High |
| < 50% | ❌ REJECT | N/A | Event-driven only | N/A |

---

## Post-Retraining Checklist

After executing `python models/retrain_clean.py`:

- [ ] Walk-forward accuracy displayed (should be 52-58%)
- [ ] Model saved: `models/model_clean_YYYYMMDD_HHMMSS.pkl`
- [ ] Metadata saved: `models/model_clean_metadata_YYYYMMDD_HHMMSS.json`
- [ ] Review metadata: `cat models/model_clean_metadata_*.json | grep accuracy`
- [ ] Decision made based on accuracy
- [ ] If > 58%: Ready for deployment
- [ ] If 52-58%: Ready for monitored deployment
- [ ] If < 50%: Prepare event-driven fallback

---

## Deployment Commands (if approved)

### If Accuracy ≥ 52%:

```bash
# 1. Copy model to current
cp models/model_clean_YYYYMMDD_HHMMSS.pkl models/model_current.pkl

# 2. Update confidence (58-65% → 0.60, 52-58% → 0.70)
# Edit core/config.py:
# ML_SIGNAL_CONFIDENCE_MIN = 0.60 (or 0.70)

# 3. Commit to git
git add models/model_current.pkl core/config.py
git commit -m "DEPLOY: Clean model v2 with LAG(1) features"

# 4. Push to EC2
scp models/model_current.pkl ubuntu@52.90.60.32:/home/ubuntu/opticore-bot/models/
scp core/config.py ubuntu@52.90.60.32:/home/ubuntu/opticore-bot/core/

# 5. Restart service
ssh ubuntu@52.90.60.32 "systemctl restart opticore"
```

---

## Risk Management

| Scenario | Risk Level | Mitigation |
|---|---|---|
| Deploy without walk-forward test | 🔴 CRITICAL | ✅ Already planned (6-fold CV) |
| Deploy with > 65% accuracy | 🔴 CRITICAL | ✅ Decision tree (investigate first) |
| Deploy with 50-52% accuracy | 🟠 HIGH | ✅ Paper trade 30 days first |
| Deploy with < 50% accuracy | 🔴 CRITICAL | ✅ Decision tree (reject) |
| Use old leaky model | 🔴 CRITICAL | ✅ Replaced with clean version |

---

## Key Insights

### Why we expect 52-58%?
- Random guess: 50%
- Real trading edge with clean features: 52-58%
- Overfitted model (old): 99.98%
- The 52-58% is realistic, honest, tradeable

### Why not 80%+?
- Markets are noisy
- Many unpredictable factors
- Even professional traders target 55-60% win rates
- Too-high accuracy indicates overfitting/leakage

### What if we get 65%?
- Check if lag(1) actually applied
- Verify no price features in training
- Run diagnostic tests again
- Consider: Different data period, market regime change

---

## Next Actions

1. **Execute:** `python models/retrain_clean.py` (3-5 min)
2. **Observe:** Walk-forward accuracy output
3. **Decide:** Based on result, follow decision tree
4. **Deploy:** If ≥52%, proceed with deployment
5. **Monitor:** Track actual win rate for 30+ trades

**Ready to proceed?** Run: `python models/retrain_clean.py`
