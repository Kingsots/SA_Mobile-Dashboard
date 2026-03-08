#!/usr/bin/env python3
"""
Debug script to test lag1 feature creation and signal generation
"""
import sys
import pandas as pd
import numpy as np
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from signals.xgb_signal_engine import XGBoostSignalEngine
from core.database import Database
from core.config import Config

def test_lag1_creation():
    """Test that lag1 features are being created correctly"""
    
    print("\n" + "="*80)
    print("LAG1 FEATURE CREATION TEST")
    print("="*80)
    
    # Create synthetic data to test lag1 creation
    test_data = pd.DataFrame({
        'ema_21': [100.0, 101.0, 102.0, 103.0, 104.0],
        'ema_100': [99.0, 100.0, 101.0, 102.0, 103.0],
        'rsi_14': [50.0, 52.0, 54.0, 56.0, 58.0],
        'obv': [1000.0, 1100.0, 1200.0, 1300.0, 1400.0],
        'ad': [500.0, 510.0, 520.0, 530.0, 540.0],
        'vwap_slope': [0.5, 0.6, 0.7, 0.8, 0.9],
        'volume_sma_20': [1000.0, 1050.0, 1100.0, 1150.0, 1200.0],
        'volume_ratio': [0.95, 0.96, 0.97, 0.98, 0.99],
    })
    
    print(f"\n✓ Test data created with {len(test_data)} rows")
    print(f"  Columns: {test_data.columns.tolist()}")
    
    # Initialize signal engine
    engine = XGBoostSignalEngine()
    
    # Test prepare_features_for_inference
    prepared = engine.prepare_features_for_inference(test_data)
    
    print(f"\n✓ Features prepared for inference")
    print(f"  Prepared data columns: {prepared.columns.tolist()}")
    
    # Check lag1 values
    lag1_cols = ['ema_21_lag1', 'ema_100_lag1', 'rsi_14_lag1', 'obv_lag1', 
                 'ad_lag1', 'vwap_slope_lag1', 'volume_sma_20_lag1', 'volume_ratio_lag1']
    
    print(f"\n✓ Lag1 values (last row):")
    for col in lag1_cols:
        if col in prepared.columns:
            val = prepared[col].iloc[-1]
            status = "NaN" if pd.isna(val) else f"{val:.2f}"
            print(f"  {col:25} = {status}")
    
    # Check if any lag1 values are NaN in the last row
    last_row = prepared.iloc[-1]
    nan_lag1_cols = [col for col in lag1_cols if col in prepared.columns and pd.isna(last_row[col])]
    
    if nan_lag1_cols:
        print(f"\n⚠️  WARNING: NaN values in lag1 columns: {nan_lag1_cols}")
        print("   This will cause model inference to fail")
    else:
        print(f"\n✅ All lag1 values are valid (no NaN)")

def test_model_inference():
    """Test model inference with lag1 features"""
    
    print("\n" + "="*80)
    print("MODEL INFERENCE TEST")
    print("="*80)
    
    engine = XGBoostSignalEngine()
    
    if engine.model is None:
        print("\n⚠️  Model not loaded - skipping inference test")
        return
    
    # Create test data with lag1 features
    test_data = pd.DataFrame({
        'ema_21': [102.5],
        'ema_100': [101.5],
        'rsi_14': [55.0],
        'obv': [1250.0],
        'ad': [525.0],
        'vwap_slope': [0.75],
        'volume_sma_20': [1125.0],
        'volume_ratio': [0.97],
        # Lag1 values
        'ema_21_lag1': [101.5],
        'ema_100_lag1': [100.5],
        'rsi_14_lag1': [53.0],
        'obv_lag1': [1150.0],
        'ad_lag1': [515.0],
        'vwap_slope_lag1': [0.65],
        'volume_sma_20_lag1': [1075.0],
        'volume_ratio_lag1': [0.96],
    })
    
    print(f"\n✓ Test data with lag1 features created ({len(test_data)} rows)")
    
    try:
        signal, confidence = engine.predict_signal(test_data)
        print(f"\n✅ Model inference successful")
        print(f"   Signal: {signal:+d} ({'BUY' if signal > 0 else 'SELL' if signal < 0 else 'NEUTRAL'})")
        print(f"   Confidence: {confidence:.2%}")
    except Exception as e:
        print(f"\n❌ Model inference failed: {e}")
        import traceback
        traceback.print_exc()

def test_database_features():
    """Test loading features from database"""
    
    print("\n" + "="*80)
    print("DATABASE FEATURES TEST")
    print("="*80)
    
    db = Database()
    
    # Try to load features for a specific ticker
    ticker = 'EURUSD'
    interval = '30m'
    
    try:
        df = db.load_features(ticker, interval, days=1)
        
        if df is None or df.empty:
            print(f"\n⚠️  No features found for {ticker} {interval}")
        else:
            print(f"\n✓ Loaded {len(df)} rows for {ticker} {interval}")
            print(f"  Columns: {df.columns.tolist()}")
            
            # Check for lag1 columns
            lag1_cols = ['ema_21_lag1', 'ema_100_lag1', 'rsi_14_lag1', 'obv_lag1', 
                         'ad_lag1', 'vwap_slope_lag1', 'volume_sma_20_lag1', 'volume_ratio_lag1']
            
            available_lag1 = [col for col in lag1_cols if col in df.columns]
            print(f"\n✓ Lag1 columns found: {len(available_lag1)}/{len(lag1_cols)}")
            
            # Check last row for NaN values
            last_row = df.iloc[-1]
            nan_cols = [col for col in df.columns if pd.isna(last_row[col])]
            
            if nan_cols:
                print(f"\n⚠️  NaN values in last row: {nan_cols}")
            else:
                print(f"\n✅ Last row has no NaN values")
            
            # Show lag1 values in last row
            print(f"\n✓ Lag1 values (last row):")
            for col in lag1_cols:
                if col in df.columns:
                    val = last_row[col]
                    status = "NaN" if pd.isna(val) else f"{val:.2f}"
                    print(f"  {col:25} = {status}")
                    
    except Exception as e:
        print(f"\n❌ Database query failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_lag1_creation()
    test_model_inference()
    test_database_features()
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80 + "\n")
