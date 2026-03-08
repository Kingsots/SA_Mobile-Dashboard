import sys
sys.path.insert(0, '.')
from signals.xgb_signal_engine import XGBSignalEngine
import pandas as pd
import numpy as np

# Create engine
engine = XGBSignalEngine()

# Create fake features (30 rows)
np.random.seed(42)
data = {
    'timestamp': pd.date_range('2026-01-01', periods=30, freq='4h'),
    'ticker': 'EURUSD',
    'interval': '4h',
    'open': np.random.uniform(1.07, 1.09, 30),
    'high': np.random.uniform(1.08, 1.10, 30),
    'low': np.random.uniform(1.06, 1.08, 30),
    'close': np.random.uniform(1.07, 1.09, 30),
    'volume': np.random.uniform(100000, 200000, 30),
    'ema_21': np.random.uniform(1.07, 1.09, 30),
    'ema_100': np.random.uniform(1.07, 1.09, 30),
    'rsi_14': np.random.uniform(40, 60, 30),
    'obv': np.random.uniform(1000000, 2000000, 30),
    'ad': np.random.uniform(500000, 1500000, 30),
    'vwap': np.random.uniform(1.07, 1.09, 30),
    'vwap_slope': np.random.uniform(-0.001, 0.001, 30),
    'volume_sma_20': np.random.uniform(100000, 200000, 30),
    'volume_ratio': np.random.uniform(0.8, 1.2, 30),
}

df_features = pd.DataFrame(data)
print("Created test DataFrame with columns:", list(df_features.columns))

# Test prepare_features_for_inference
try:
    df_with_lags = engine.prepare_features_for_inference(df_features)
    print(f"✅ prepare_features_for_inference works!")
    print(f"   Original columns: {len(df_features.columns)}")
    print(f"   After lag creation: {len(df_with_lags.columns)}")
    
    lag_cols = [col for col in df_with_lags.columns if 'lag1' in col]
    print(f"   Lag1 columns created: {lag_cols}")
except Exception as e:
    print(f"❌ Error in prepare_features_for_inference: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test predict_signal
try:
    signal, confidence = engine.predict_signal(df_with_lags)
    print(f"✅ predict_signal works!")
    print(f"   Signal: {signal}, Confidence: {confidence:.2%}")
except Exception as e:
    print(f"❌ Error in predict_signal: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✅ All tests passed!")
