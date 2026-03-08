#!/usr/bin/env python3
"""
Diagnose why model is predicting only NEUTRAL signals.
Tests the lag1 feature creation and model inference paths.
"""

import pandas as pd
import numpy as np
import sqlite3
import joblib
from datetime import datetime, timezone
import logging

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_lag1_creation():
    """Test if shift(1) properly creates lag1 features with small DataFrames"""
    print("\n" + "="*80)
    print("TEST 1: LAG1 CREATION WITH SMALL DATAFRAMES")
    print("="*80)
    
    # Test with 2 rows (what shift needs)
    df = pd.DataFrame({
        'ema_21': [100.5, 101.2],
        'ema_100': [99.8, 100.1],
        'rsi_14': [55.3, 56.1],
        'obv': [1000000, 1050000],
        'ad': [500000, 520000],
        'vwap_slope': [0.5, 0.6],
        'volume_sma_20': [100000, 105000],
        'volume_ratio': [1.2, 1.3],
    })
    
    print(f"\nInput DataFrame (2 rows):")
    print(df)
    
    # Create lag1
    for col in df.columns:
        df[f'{col}_lag1'] = df[col].shift(1)
    
    print(f"\nAfter shift(1):")
    print(df[['ema_21', 'ema_21_lag1', 'ema_100', 'ema_100_lag1']])
    
    print(f"\nLag1 values in row 0: {df[['ema_21_lag1', 'ema_100_lag1', 'rsi_14_lag1']].iloc[0].to_dict()}")
    print(f"Lag1 values in row 1: {df[['ema_21_lag1', 'ema_100_lag1', 'rsi_14_lag1']].iloc[1].to_dict()}")
    print(f"✅ Row 1 has valid lag1 values? {df[['ema_21_lag1', 'ema_100_lag1']].iloc[1].notna().all()}")
    
    return df

def test_model_inference():
    """Test if model can actually predict BUY/SELL"""
    print("\n" + "="*80)
    print("TEST 2: MODEL INFERENCE")
    print("="*80)
    
    try:
        # Load the model - try multiple locations
        model_paths = [
            'trading_model.pkl',
            'data/models/trading_model.pkl',
            'data/models/model_current.pkl',
            'models/model_clean_20260106_082033.pkl'
        ]
        
        model = None
        for path in model_paths:
            try:
                model = joblib.load(path)
                print(f"✅ Model loaded from: {path}")
                break
            except FileNotFoundError:
                continue
        
        if model is None:
            raise FileNotFoundError(f"Model not found in any path: {model_paths}")
        print(f"✅ Model loaded successfully")
        print(f"   Model type: {type(model)}")
        print(f"   Classes: {model.classes_ if hasattr(model, 'classes_') else 'N/A'}")
        
        # Create synthetic lag1 features
        lag1_cols = [
            'ema_21_lag1', 'ema_100_lag1', 'rsi_14_lag1',
            'volume_sma_20_lag1', 'volume_ratio_lag1',
            'obv_lag1', 'ad_lag1', 'vwap_slope_lag1'
        ]
        
        # Synthetic data for BUY signal (uptrend features)
        X_buy = pd.DataFrame({
            'ema_21_lag1': [102.0],
            'ema_100_lag1': [101.5],
            'rsi_14_lag1': [65.0],  # Overbought but rising
            'volume_sma_20_lag1': [120000],
            'volume_ratio_lag1': [1.5],
            'obv_lag1': [1100000],
            'ad_lag1': [550000],
            'vwap_slope_lag1': [0.8],
        })
        
        # Synthetic data for SELL signal (downtrend)
        X_sell = pd.DataFrame({
            'ema_21_lag1': [98.0],
            'ema_100_lag1': [98.5],
            'rsi_14_lag1': [35.0],  # Oversold and falling
            'volume_sma_20_lag1': [80000],
            'volume_ratio_lag1': [0.8],
            'obv_lag1': [900000],
            'ad_lag1': [450000],
            'vwap_slope_lag1': [-0.6],
        })
        
        # Neutral data
        X_neutral = pd.DataFrame({
            'ema_21_lag1': [100.5],
            'ema_100_lag1': [100.0],
            'rsi_14_lag1': [50.0],  # Neutral
            'volume_sma_20_lag1': [100000],
            'volume_ratio_lag1': [1.0],
            'obv_lag1': [1000000],
            'ad_lag1': [500000],
            'vwap_slope_lag1': [0.0],
        })
        
        print(f"\n📊 Testing with synthetic data:")
        
        for label, X in [("BUY trend", X_buy), ("SELL trend", X_sell), ("NEUTRAL", X_neutral)]:
            pred = model.predict(X)[0]
            proba = model.predict_proba(X)[0]
            
            # Map 0->SELL(-1), 1->BUY(+1)
            signal_map = {0: -1, 1: 1}
            signal = signal_map.get(pred, 0)
            confidence = proba.max()
            
            print(f"\n   {label}:")
            print(f"      Raw prediction: {pred} (classes: {model.classes_})")
            print(f"      Probabilities: {proba}")
            print(f"      Signal: {signal} (BUY=1, SELL=-1, NEUTRAL=0)")
            print(f"      Confidence: {confidence:.2%}")
            
    except Exception as e:
        print(f"❌ Model inference failed: {e}")
        import traceback
        traceback.print_exc()

def test_database_features():
    """Check what features are actually in the database"""
    print("\n" + "="*80)
    print("TEST 3: DATABASE FEATURE INSPECTION")
    print("="*80)
    
    try:
        conn = sqlite3.connect('trading_bot.db')
        cursor = conn.cursor()
        
        # Check table schema
        cursor.execute("PRAGMA table_info(features)")
        columns = cursor.fetchall()
        
        print(f"\n📋 Features table columns:")
        col_names = [col[1] for col in columns]
        
        # Check for lag1 columns
        lag1_cols = [col for col in col_names if '_lag1' in col]
        print(f"   Total columns: {len(col_names)}")
        print(f"   Lag1 columns: {len(lag1_cols)} - {lag1_cols}")
        
        # Get latest feature row
        cursor.execute("""
            SELECT created_at, ema_21, ema_100, rsi_14,
                   ema_21_lag1, ema_100_lag1, rsi_14_lag1
            FROM features
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        if result:
            print(f"\n📊 Latest feature row:")
            print(f"   Timestamp: {result[0]}")
            print(f"   Base features: ema_21={result[1]}, ema_100={result[2]}, rsi_14={result[3]}")
            print(f"   Lag1 features: ema_21_lag1={result[4]}, ema_100_lag1={result[5]}, rsi_14_lag1={result[6]}")
            
            has_nans = any(v is None for v in result[4:7])
            print(f"   Has NaN lag1? {has_nans}")
        else:
            print(f"   ❌ No features found in database")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Database inspection failed: {e}")
        import traceback
        traceback.print_exc()

def test_database_signals():
    """Check recent signals in database"""
    print("\n" + "="*80)
    print("TEST 4: DATABASE SIGNALS INSPECTION")
    print("="*80)
    
    try:
        conn = sqlite3.connect('trading_bot.db')
        cursor = conn.cursor()
        
        # Get latest signals
        cursor.execute("""
            SELECT ticker, signal, confidence, triggered_by, created_at
            FROM ml_signals
            ORDER BY created_at DESC
            LIMIT 10
        """)
        
        signals = cursor.fetchall()
        
        print(f"\n📊 Last 10 signals:")
        signal_names = {0: "NEUTRAL", 1: "BUY", -1: "SELL"}
        
        neutral_count = 0
        for ticker, signal, conf, trigger, ts in signals:
            signal_name = signal_names.get(signal, f"UNKNOWN({signal})")
            print(f"   {ts}: {ticker} {signal_name} conf={conf:.2%} ({trigger})")
            if signal == 0:
                neutral_count += 1
        
        print(f"\n⚠️  Statistics:")
        print(f"   Total: {len(signals)}")
        print(f"   Neutral: {neutral_count}/{len(signals)} ({100*neutral_count/len(signals):.1f}%)")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Signal inspection failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("\n🔍 DIAGNOSING MODEL PREDICTION ISSUE")
    print(f"   Timestamp: {datetime.now(timezone.utc).isoformat()}")
    
    # Run all tests
    test_lag1_creation()
    test_model_inference()
    test_database_features()
    test_database_signals()
    
    print("\n" + "="*80)
    print("DIAGNOSIS COMPLETE")
    print("="*80)
