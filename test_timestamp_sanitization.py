"""
Test timestamp sanitization in feature snapshot
Validates that datetime/Timestamp objects are properly filtered out
"""

import pandas as pd
import numpy as np
from datetime import datetime

def test_sanitization():
    """Test the sanitization logic from xgb_signal_engine.py"""
    
    # Simulate a feature_snapshot with mixed types including timestamps
    features_snapshot = {
        'ema_21': 1.234,
        'ema_100': 1.456,
        'rsi_14': 67.8,
        'timestamp': pd.Timestamp('2025-11-10 09:00:00'),  # This should be filtered
        'created_at': datetime(2025, 11, 10, 9, 0, 0),     # This should be filtered
        'volume': 1000000,
        'close': 1.2345,
        'nan_value': np.nan,
        'numpy_int': np.int64(42),
    }
    
    print("Original features_snapshot:")
    for k, v in features_snapshot.items():
        print(f"  {k}: {v} (type: {type(v).__name__})")
    
    # Check for timestamp fields (Step 2 - Debug logging)
    timestamp_fields = [k for k, v in features_snapshot.items() 
                       if isinstance(v, (pd.Timestamp, datetime))]
    if timestamp_fields:
        print(f"\n⚠️  Timestamp fields detected: {timestamp_fields}")
    
    # Apply sanitization (Step 1)
    clean_snapshot = {
        k: (float(v) if pd.notna(v) and not isinstance(v, (pd.Timestamp, datetime)) else None)
        for k, v in features_snapshot.items()
        if not isinstance(v, (pd.Timestamp, datetime))
    }
    
    print("\n✅ Cleaned snapshot (timestamps removed):")
    for k, v in clean_snapshot.items():
        print(f"  {k}: {v} (type: {type(v).__name__ if v is not None else 'NoneType'})")
    
    # Validation checks
    assert 'timestamp' not in clean_snapshot, "timestamp should be removed"
    assert 'created_at' not in clean_snapshot, "created_at should be removed"
    assert clean_snapshot['ema_21'] == 1.234, "ema_21 should be preserved"
    assert clean_snapshot['rsi_14'] == 67.8, "rsi_14 should be preserved"
    assert clean_snapshot['nan_value'] is None, "NaN should become None"
    assert clean_snapshot['numpy_int'] == 42.0, "numpy int should convert to float"
    
    print("\n✅ All validation checks passed!")
    print(f"✅ Reduced from {len(features_snapshot)} to {len(clean_snapshot)} features")
    print(f"✅ Removed {len(timestamp_fields)} timestamp fields")
    
    return clean_snapshot

if __name__ == '__main__':
    result = test_sanitization()
    print("\n" + "="*60)
    print("SANITIZATION TEST SUCCESSFUL")
    print("="*60)
