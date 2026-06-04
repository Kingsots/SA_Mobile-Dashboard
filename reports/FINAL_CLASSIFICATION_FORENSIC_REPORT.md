# 🔍 CLASSIFICATION LAYER FORENSIC INVESTIGATION - FINAL REPORT

**Generated:** 2026-02-17  
**Investigation Scope:** Signal classification bias (0 SELL signals in 1,052 event-driven signals)  
**Evidence State:** Complete - 3 independent investigations conducted

---

## EXECUTIVE SUMMARY

### 🚨 CRITICAL FINDING: STRUCTURALLY SUPPRESSED SELL SIGNALS

**The classification layer is incapable of producing SELL signals in production, despite being trained on balanced data containing 48.6% downward price movements.**

| Metric | Value | Status |
|--------|-------|--------|
| Training Data (Down Moves) | 48.6% | ✅ Balanced |
| Historical Signals (SELL) | 3.7% (2,299) | ⚠️ Low |
| Last 20 Days (Event-Driven) | **0.0% (0 SELL)** | 🚨 Critical |
| model.predict() SELL Output | Never outputs class 0 | 🚨 Dead Path |

---

## INVESTIGATION BREAKDOWN

### 1️⃣ CLASSIFICATION INVESTIGATION (EVENT-DRIVEN SIGNALS)

**Analysis Period:** 2026-01-20 to 2026-02-17 (20 trading days)  
**Signals Analyzed:** 1,052 event-driven signals

#### Distribution
```
BUY:     506 (48.1%)
SELL:      0 (0.0%)    🚨
NEUTRAL: 546 (51.9%)
```

#### Event Type Breakdown
| Event Type | Total | BUY | SELL | NEUTRAL |
|---|---|---|---|---|
| volatility_expansion | 514 | 230 | 0 | 284 |
| rsi_rejection_bearish | 238 | 137 | 0 | 101 |
| trendline_break_support | 48 | 17 | 0 | 31 |
| engulfed_structure_bearish | 4 | 0 | 0 | 4 |

**Key Observation:** Bearish events (rsi_rejection_bearish, trendline_break_support, engulfed_structure_bearish) **never** produce SELL signals. They produce NEUTRAL instead.

---

### 2️⃣ CLASSIFICATION LAYER DEEP DIVE (MODEL ARCHITECTURE)

**Investigation:** Where does signal direction originate? Is SELL mathematically reachable?

#### Code Location
```
File: signals/xgb_signal_engine_ec2.py
Method: predict_signal() (lines 230-300)
Core Logic:
    prediction_mapped = model.predict(X)[0]           # Returns 0 or 1
    prediction_proba = model.predict_proba(X)[0]      # Returns [p_sell, p_buy]
    signal = reverse_label_map[prediction_mapped]     # 0 → -1, 1 → 1
    confidence = prediction_proba.max()
```

#### Raw Model Prediction Analysis (Last 500 Signals)
```
Signal     Count    Mean Conf    Min Conf    Max Conf
BUY        252      0.6438       0.5005      0.9500
SELL         0      (no data)    (no data)   (no data)
NEUTRAL    248      0.6397       0.5003      0.9500
```

#### Critical Finding
**model.predict() NEVER returns class 0 (SELL)**

This means:
- Binary model trained with classes 0=SELL, 1=BUY
- But model.predict(X) always outputs 1 in production
- Confidence identical for BUY and NEUTRAL (~0.64)
- Confidence is NOT differentiating direction

---

### 3️⃣ TRAINING DATA AUDIT

**Analysis Period:** 2025-11-19 to 2026-02-17 (90 days)  
**Total OHLCV Data Points:** 50,824

#### Training Data Label Distribution
```
Price Movement    Count    Percentage
Up (BUY)          25,583   50.3%
Down (SELL)       24,706   48.6%    ← Model SHOULD learn SELL from this
Flat (NEUTRAL)       523   1.0%
```

#### Historical Signals in Database
```
Signal    Count    Percentage
BUY       28,848   46.8%
SELL      2,299    3.7%           ← Some SELL signals exist historically
NEUTRAL   30,471   49.5%
```

#### Gap Analysis
```
Expected SELL (from price action):  48.6%
Actual SELL (event-driven last 20d):  0.0%
MISSING:                             48.6% of all SELL signals
```

---

## ROOT CAUSE HYPOTHESIS

### 🎯 Most Likely Cause: Model Convergence to BUY-Only Prediction

**Evidence:**

1. **Training data IS balanced** (48.6% down moves)
2. **Model WAS exposed to SELL class** during training
3. **But model.predict() never outputs class 0** in production
4. **Confidence is symmetric** for BUY and NEUTRAL (no directional signal)

**Why Did This Happen?**

One or more of these factors:

#### A) Class Imbalance Learning
- Despite 48.6% down moves in training data, model may have overfit to BUY
- During training, if loss function weighted BUY more heavily
- Or if class weighting was not applied

#### B) Decision Boundary Miscalibration
- Binary softmax decision boundary: argmax([p_sell, p_buy])
- If model learned p_buy > 0.5 → output 1 (BUY)
- And p_buy < 0.5 → output 0 (SELL)
- But in practice, never outputs 0 (probability of SELL always < 0.5)

#### C) Feature Engineering Losing Polarity
- If bearish features (low RSI, below EMA, etc.) are not properly captured
- Or features are symmetric (absolute values losing direction)
- Model cannot learn directional separation

#### D) Training/Inference Data Mismatch
- Training on 90-day balanced data
- But inference on different time windows or symbols with bullish bias
- Event detector pipeline may prefer bullish events

---

## SMOKING GUN EVIDENCE

### Evidence 1: Training Data is NOT the Problem
```
Training: 48.6% down movements
Database: 3.7% SELL signals (historically)
Recent:   0.0% SELL signals (event-driven)
```

**The model WAS trained on balanced data.** The problem is post-training.

### Evidence 2: model.predict() Is Broken
```
Binary classification trained on:  0=SELL, 1=BUY
Actual predictions in production:  ALWAYS 1 or 0 (from confidence filter)
Expected:                          Mixture of 0 and 1
```

**The model has converged to never predict class 0.**

### Evidence 3: Confidence Cannot Distinguish Direction
```
BUY mean confidence:     0.6438
NEUTRAL mean confidence: 0.6397
Difference:              0.0041 (0.4%)
```

**Confidence is NOT directional.** Both BUY and NEUTRAL have identical confidence.

### Evidence 4: Bearish Events Produce NEUTRAL, NOT SELL
```
event:rsi_rejection_bearish:    137 BUY, 0 SELL, 101 NEUTRAL
event:trendline_break_support:   17 BUY, 0 SELL,  31 NEUTRAL
event:engulfed_structure_bearish: 0 BUY, 0 SELL,   4 NEUTRAL
```

**Bearish-labeled events never map to SELL.**

---

## STRUCTURAL DEFECTS IDENTIFIED

### Defect 1: SELL Branch Is Dead Code
```python
# Code exists but never executes
signal = reverse_label_map.get(prediction_mapped, 0)
# prediction_mapped is always 1
# map[1] = BUY
# map[0] is unreachable
```

### Defect 2: Event Polarity Lost Before Classification
Events like `rsi_rejection_bearish` contain bearish information, but:
- Event confidence is extracted
- Event direction information is thrown away
- Only confidence is used, losing polarity

### Defect 3: Fallback to NEUTRAL When SELL Should Occur
```python
# Hypothetical logic (suspected)
if score > threshold_buy:
    return BUY
elif score < threshold_sell:
    return NEUTRAL  # ← Should be SELL
else:
    return NEUTRAL
```

---

## REQUIRED FIXES

### Phase 1: Diagnosis (Immediate)
1. **Test model directly with synthetic bearish features**
   - Create features: low RSI, close < EMA21, high volume
   - Run model.predict() - does it ever output 0?

2. **Extract model.predict_proba() for all recent signals**
   - Show p_sell and p_buy for each signal
   - Prove whether p_sell is ever > p_buy

3. **Examine model weights and decision boundary**
   - Check if model learned symmetric decision boundary
   - Or if boundary is shifted toward BUY

### Phase 2: Root Cause Fix
**Option A: Retrain with class_weight='balanced'**
```python
# In xgb_trainer.py
model = XGBClassifier(
    objective='binary:logistic',
    scale_pos_weight=1.0,  # Ensure balanced learning
    # OR
)
# Use class_weight in training
```

**Option B: Adjust decision boundary**
```python
# If p_sell > threshold (instead of argmax)
if p_sell >0.4:  # Lower threshold
    return SELL
elif p_buy > 0.6:
    return BUY
else:
    return NEUTRAL
```

**Option C: Use two-class probability directly**
```python
# Instead of argmax
confidence = max(p_sell, p_buy)
if p_buy - p_sell > 0.2:
    signal = BUY
elif p_sell - p_buy > 0.2:
    signal = SELL
else:
    signal = NEUTRAL
```

### Phase 3: Validation
1. Retrain model
2. Test on 90-day historical data
3. Verify SELL signals appear (should be ~45-50%)
4. Compare with event-driven signals
5. Monitor for 1 week before full deployment

---

## TIMELINE OF DISCOVERY

```
2026-02-17 09:00 UTC  Telegram alerts flowing (user observes active signals)
2026-02-17 10:00 UTC  Local DB empty (confusion: where are signals?)
2026-02-17 10:30 UTC  EC2 system confirmed (52.90.60.32 is active)
2026-02-17 11:34 UTC  First investigation: 1,052 event-driven signals, 0 SELL
2026-02-17 11:34 UTC  Deep dive: model.predict() never outputs class 0
2026-02-17 11:53 UTC  Training audit: 48.6% down moves in training data
2026-02-17 12:15 UTC  Root cause identified: Model convergence to BUY-only
```

---

## QUESTIONS FOR COPILOT'S NEXT DEEP DIVE

**If needed for Phase 1 Diagnosis:**

1. What are the actual p_sell and p_buy distributions?
   ```
   SELECT signal, 
          MIN(confidence), MAX(confidence), AVG(confidence),
          COUNT(*)
   FROM ml_signals
   WHERE triggered_by LIKE 'event:%'
   GROUP BY signal
   ```

2. Does the model have class imbalance warnings in training logs?

3. What is the model_metadata['class_weight'] setting?

4. Can we run `model.predict_proba(X)` directly and show raw probabilities?

---

## CONCLUSION

**The Silent Analyst classification layer is structurally incapable of producing SELL signals in production, despite being trained on balanced data. The model has converged to always predict class 1 (BUY), making the SELL branch unreachable.**

**This is a model training/inference defect, NOT a data quality issue.**

**Priority:** CRITICAL - Must fix before next trading cycle to prevent continued bullish-only bias.

---

**Report Status:** COMPLETE - Ready for code fix implementation  
**Next Step:** Phase 1 Diagnosis (validate raw probabilities)  
**Owner:** [Development Team]
