"""
DIAGNOSTIC TEST 3: Walk-Forward Validation

Simulate realistic trading conditions: train on historical data, test on future data.
This is the ONLY way to detect leakage with time-series data.

Splits data into 6 folds chronologically:
  Fold 1: Train on days 1-14,  test on day 15
  Fold 2: Train on days 1-28,  test on days 29-30
  Fold 3: Train on days 1-44,  test on days 45-47
  ... etc

Expected accuracy:
  - If leakage present (model uses next_close): >95%
  - If clean (model uses true features): 52-58%
"""

import sqlite3
import pandas as pd
import numpy as np
import joblib
import warnings
from pathlib import Path
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import xgboost as xgb

warnings.filterwarnings('ignore')

print("=" * 70)
print("DIAGNOSTIC TEST 3: WALK-FORWARD VALIDATION")
print("=" * 70)

# Load features from database
db_path = Path("trading_bot.db")
if not db_path.exists():
    print(f"❌ Database not found at {db_path}")
    exit(1)

try:
    conn = sqlite3.connect(str(db_path))
    query = """
    SELECT * FROM features 
    WHERE ticker = 'AUDCAD' AND interval = '1h'
    ORDER BY timestamp ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    print(f"✅ Loaded {len(df)} feature rows from database")
except Exception as e:
    print(f"❌ Error loading features: {e}")
    exit(1)

# Prepare features
feature_cols = ['open', 'high', 'low', 'close', 'ema_21', 'ema_100', 'rsi_14',
                'volume', 'volume_sma_20', 'volume_ratio', 'obv', 'ad', 'vwap', 'vwap_slope']

available_cols = [col for col in feature_cols if col in df.columns]

try:
    df['next_close'] = df['close'].shift(-1)
    df['target'] = np.where(df['next_close'] > df['close'], 1, 0)  # Convert to 0/1
    df = df.dropna()
    
    X = df[available_cols].astype(np.float32)
    y = df['target']
    
    print(f"✅ Prepared {X.shape[0]} samples with {X.shape[1]} features")
except Exception as e:
    print(f"❌ Error preparing features: {e}")
    exit(1)

# Walk-forward validation: 6 folds
n_samples = len(X)
fold_size = n_samples // 7  # 6 folds + 1 leftover

print(f"\n{len(X)} total samples → 6-fold walk-forward ({fold_size} samples/fold)")

results = []

for fold_idx in range(6):
    # Split point: train on 1-5 folds, test on fold 6
    train_end = (fold_idx + 1) * fold_size
    test_end = min(train_end + fold_size, n_samples)
    
    X_train = X.iloc[:train_end]
    y_train = y.iloc[:train_end]
    X_test = X.iloc[train_end:test_end]
    y_test = y.iloc[train_end:test_end]
    
    try:
        # Train XGBoost (use -1/1 binary classification)
        model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=7,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbosity=0,
            eval_metric='logloss'
        )
        model.fit(X_train, y_train, verbose=False)
        
        # Evaluate
        y_pred = model.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        
        results.append({
            'fold': fold_idx + 1,
            'train_size': len(X_train),
            'test_size': len(X_test),
            'accuracy': acc,
            'precision': prec,
            'recall': rec,
            'f1': f1
        })
        
        print(f"Fold {fold_idx+1}: train {len(X_train):5d}, test {len(X_test):5d} → " 
              f"ACC {acc:.1%}, PREC {prec:.1%}, REC {rec:.1%}, F1 {f1:.1%}")
    except Exception as e:
        print(f"❌ Fold {fold_idx+1} failed: {e}")

# Summary statistics
print("\n" + "=" * 70)
print("WALK-FORWARD RESULTS SUMMARY")
print("=" * 70)

if results:
    results_df = pd.DataFrame(results)
    mean_acc = results_df['accuracy'].mean()
    std_acc = results_df['accuracy'].std()
    min_acc = results_df['accuracy'].min()
    max_acc = results_df['accuracy'].max()
    
    print(f"\nAccuracy Statistics:")
    print(f"  Mean:  {mean_acc:.1%}")
    print(f"  Std:   {std_acc:.1%}")
    print(f"  Min:   {min_acc:.1%}")
    print(f"  Max:   {max_acc:.1%}")
    
    print(f"\n" + "=" * 70)
    print("LEAKAGE ASSESSMENT")
    print("=" * 70)
    
    if mean_acc > 0.90:
        print("\n🚨 SEVERE LEAKAGE DETECTED")
        print(f"   Mean accuracy {mean_acc:.1%} is too high (>90%)")
        print("   Model is using information it shouldn't have")
        print("   Recommendation: Remove direct price features and retrain")
    elif mean_acc > 0.70:
        print("\n⚠️  MODERATE LEAKAGE SUSPECTED")
        print(f"   Mean accuracy {mean_acc:.1%} is higher than expected (>70%)")
        print("   Some features may contain leaked information")
        print("   Recommendation: Review feature importance, consider retraining")
    elif mean_acc > 0.60:
        print("\n✅ MILD LEAKAGE (ACCEPTABLE)")
        print(f"   Mean accuracy {mean_acc:.1%} is in range for real model")
        print("   Model shows slight predictive edge but not suspicious")
        print("   Recommendation: Proceed with caution, monitor performance")
    else:
        print("\n✅ NO LEAKAGE DETECTED")
        print(f"   Mean accuracy {mean_acc:.1%} is realistic (random guess ~50%)")
        print("   Model has minimal predictive power")
        print("   Recommendation: Review feature set, may need enhancement")
    
    print("\n" + "=" * 70)
    print("INTERPRETATION GUIDE")
    print("=" * 70)
    print(f"""
ACCURACY THRESHOLDS:
  >90%  → SEVERE LEAKAGE (using next bar info)
  70-90% → MODERATE LEAKAGE (some future info leaked)
  60-70% → MILD LEAKAGE (slight edge, possibly accidental)
  <60%  → NO LEAKAGE (realistic trading model)

YOUR MODEL RESULT: {mean_acc:.1%}

What this means:
  - If accuracy >90%: Direct price correlation (close→next_close)
  - If accuracy 70-90%: Cumulative indicators (OBV, A/D) with future data
  - If accuracy 60-70%: Model has edge but source unclear, requires monitoring
  - If accuracy <60%: Model is honest, just weak (needs better features)

Next Steps:
  If >70%: RETRAIN with leak-proof features (remove price, OBV, A/D, VWAP)
  If <70%: OPTIMIZE feature set, add more indicators
  In all cases: Use walk-forward validation before production
""")
else:
    print("❌ No results to summarize - check errors above")
