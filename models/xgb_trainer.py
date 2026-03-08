"""
XGBoost Model Trainer
Incremental training with 90-day lookback, accuracy threshold, model versioning
"""

import pandas as pd
import numpy as np
from pathlib import Path
import joblib
import json
from datetime import datetime
import time
from typing import Dict, Tuple, Optional

from xgboost import XGBClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report

from core.config import Config
from core.database import DatabaseManager


class XGBTrainer:
    """
    XGBoost model trainer with incremental training and model versioning
    
    Training Pipeline:
    1. Load features from last 90 days
    2. Build target (next candle direction: 1=up, -1=down, 0=neutral)
    3. Time-based train/test split (80/20)
    4. Train XGBClassifier
    5. Evaluate on test set
    6. Deploy if accuracy >= 65%
    """
    
    def __init__(self):
        self.db = DatabaseManager()
        self.model_dir = Config.MODEL_DIR
        self.model_dir.mkdir(parents=True, exist_ok=True)
    
    def load_training_data(self, ticker: str = None, interval: str = None, days: int = 90) -> Optional[pd.DataFrame]:
        """
        Load features from database for training
        
        Args:
            ticker: Trading symbol (None = all symbols)
            interval: Timeframe (None = all timeframes)
            days: Number of days to load
            
        Returns:
            DataFrame with features
        """
        print(f"📥 Loading training data...")
        print(f"   Ticker: {ticker or 'ALL'}")
        print(f"   Interval: {interval or 'ALL'}")
        print(f"   Days: {days}")
        
        df = self.db.load_features(ticker, interval, days)
        
        if df is None or df.empty:
            print(f"   ❌ No features found")
            return None
        
        print(f"   ✅ Loaded {len(df)} feature rows")
        
        return df
    
    def build_target(self, df: pd.DataFrame, threshold: float = 0.0) -> pd.Series:
        """
        Build target variable (next candle direction)
        
        Target:
        - 1 (BUY):  Next candle close > current close + threshold
        - -1 (SELL): Next candle close < current close - threshold
        - 0 (NEUTRAL): Otherwise
        
        Args:
            df: DataFrame with 'close' column
            threshold: Minimum price change to trigger signal (percentage)
            
        Returns:
            Series with target values
        """
        if df is None or df.empty:
            return pd.Series()
        
        # Calculate next candle close
        next_close = df['close'].shift(-1)
        
        # Calculate percentage change
        price_change_pct = (next_close - df['close']) / df['close']
        
        # Classify direction
        target = pd.Series(0, index=df.index)  # Default: NEUTRAL
        target[price_change_pct > threshold] = 1   # BUY
        target[price_change_pct < -threshold] = -1  # SELL
        
        return target
    
    def prepare_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare feature matrix (X) and target vector (y)
        
        CRITICAL: Uses only lagged (t-1) ML features to prevent lookahead bias.
        Price features (OHLC) excluded to prevent circular prediction.
        
        Args:
            df: DataFrame with all features
            
        Returns:
            (X, y) tuple with numeric coercion applied
        """
        # ML-safe features: lagged indicators only (prevent leakage)
        # These are LAGGED by 1 bar (created in features/engine.py)
        ml_feature_cols = [
            'ema_21_lag1', 'ema_100_lag1', 'rsi_14_lag1',
            'volume_sma_20_lag1', 'volume_ratio_lag1',
            'obv_lag1', 'ad_lag1', 'vwap_slope_lag1'
        ]
        
        # Filter to available columns
        available_cols = [col for col in ml_feature_cols if col in df.columns]
        
        # Build target
        y = self.build_target(df, threshold=0.0)
        
        # Remove last row (no target available)
        X = df[available_cols].iloc[:-1].copy()
        y = y.iloc[:-1].copy()
        
        # ==========================================
        # NUMERIC COERCION - Force all to numeric, fill NaN with 0
        # ==========================================
        for col in X.columns:
            X[col] = pd.to_numeric(X[col], errors='coerce').fillna(0).astype(np.float64)
        
        # Drop neutral labels (0) and keep only BUY (1) and SELL (-1) for binary classification
        mask = y != 0
        X = X[mask]
        y = y[mask]
        
        # Additional NaN safety check
        mask = ~(X.isna().any(axis=1) | y.isna())
        X = X[mask]
        y = y[mask]
        
        print(f"\n📊 Feature Matrix:")
        print(f"   Shape: {X.shape}")
        print(f"   Features: {len(available_cols)}")
        print(f"   Samples: {len(X)}")
        print(f"\n   Target Distribution:")
        print(f"   BUY (1):     {(y == 1).sum():6} ({(y == 1).sum() / len(y) * 100:5.1f}%)")
        print(f"   SELL (-1):   {(y == -1).sum():6} ({(y == -1).sum() / len(y) * 100:5.1f}%)")
        
        return X, y
    
    def train_model(self, X: pd.DataFrame, y: pd.Series) -> Tuple[XGBClassifier, Dict]:
        """
        Train XGBoost model
        
        Args:
            X: Feature matrix
            y: Target vector
            
        Returns:
            (trained_model, metrics_dict)
        """
        print(f"\n{'='*70}")
        print(f"  🚀 TRAINING XGBOOST MODEL")
        print(f"{'='*70}\n")
        
        start_time = time.time()
        
        # Time-based train/test split
        split_idx = int(len(X) * (1 - Config.ML_TEST_SPLIT))
        
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
        
        # Remap labels for binary classification: -1 (SELL) → 0, 1 (BUY) → 1
        y_train_mapped = y_train.map({-1: 0, 1: 1})
        y_test_mapped = y_test.map({-1: 0, 1: 1})
        
        print(f"📊 Data Split:")
        print(f"   Train: {len(X_train)} samples ({len(X_train) / len(X) * 100:.1f}%)")
        print(f"   Test:  {len(X_test)} samples ({len(X_test) / len(X) * 100:.1f}%)")
        
        # Initialize model with enable_categorical=False to avoid dtype errors
        model = XGBClassifier(
            n_estimators=Config.XGBOOST_N_ESTIMATORS,
            max_depth=Config.XGBOOST_MAX_DEPTH,
            learning_rate=Config.XGBOOST_LEARNING_RATE,
            min_child_weight=Config.XGBOOST_MIN_CHILD_WEIGHT,
            subsample=Config.XGBOOST_SUBSAMPLE,
            colsample_bytree=Config.XGBOOST_COLSAMPLE_BYTREE,
            objective='binary:logistic',  # Binary: BUY vs SELL (no NEUTRAL in data)
            random_state=42,
            use_label_encoder=False,
            eval_metric='logloss',
            enable_categorical=False  # Prevent VWAP dtype errors
        )
        
        print(f"\n⚙️  Model Configuration:")
        print(f"   n_estimators: {Config.XGBOOST_N_ESTIMATORS}")
        print(f"   max_depth: {Config.XGBOOST_MAX_DEPTH}")
        print(f"   learning_rate: {Config.XGBOOST_LEARNING_RATE}")
        
        # Train model
        print(f"\n🔄 Training model...")
        
        model.fit(
            X_train, 
            y_train_mapped,
            eval_set=[(X_test, y_test_mapped)],
            verbose=False
        )
        
        training_time = time.time() - start_time
        
        # Evaluate
        y_pred_mapped = model.predict(X_test)
        
        # Map predictions back to original labels
        reverse_label_map = {0: -1, 1: 0, 2: 1}
        y_pred = pd.Series(y_pred_mapped).map(reverse_label_map)
        
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
        recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)
        f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0)
        
        print(f"\n✅ Training complete in {training_time:.2f}s")
        print(f"\n📊 Model Performance:")
        print(f"   Accuracy:  {accuracy:.2%}")
        print(f"   Precision: {precision:.2%}")
        print(f"   Recall:    {recall:.2%}")
        print(f"   F1 Score:  {f1:.2%}")
        
        # Data leakage warning for suspiciously high accuracy
        if accuracy > 0.999:
            print(f"\n⚠️  WARNING: Possible data leakage detected!")
            print(f"   Accuracy > 99.9% suggests features may be leaking future information")
            print(f"   Review feature correlation and target generation logic")
        
        # Classification report
        print(f"\n📋 Detailed Classification Report:")
        print(classification_report(
            y_test, 
            y_pred, 
            labels=[-1, 1],
            target_names=['SELL', 'BUY'],
            zero_division=0
        ))
        
        metrics = {
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'training_time': training_time,
            'timestamp': datetime.now().isoformat()
        }
        
        return model, metrics
    
    def save_model(self, model: XGBClassifier, metrics: Dict, deploy: bool = False):
        """
        Save model to disk with versioning
        
        Args:
            model: Trained XGBoost model
            metrics: Training metrics
            deploy: Whether to deploy as current model
        """
        # Generate version string
        version = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Ensure model directory exists
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # Save metadata
        metadata = {
            'version': version,
            'metrics': metrics,
            'config': {
                'n_estimators': Config.XGBOOST_N_ESTIMATORS,
                'max_depth': Config.XGBOOST_MAX_DEPTH,
                'learning_rate': Config.XGBOOST_LEARNING_RATE
            },
            'features': [
                'open', 'high', 'low', 'close', 'volume',
                'ema_21', 'ema_100', 'rsi_14',
                'obv', 'ad', 'vwap', 'vwap_slope',
                'volume_sma_20', 'volume_ratio'
            ]
        }
        
        metadata_path = Config.MODEL_METADATA_PATH
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"   ✅ Metadata saved: {metadata_path}")
        
        # Save model only if meets deployment threshold
        if deploy:
            print(f"\n💾 Saving model to disk: {Config.MODEL_CURRENT_PATH}")
            try:
                joblib.dump(model, Config.MODEL_CURRENT_PATH)
                print(f"   ✅ Model deployed: {Config.MODEL_CURRENT_PATH}")
            except Exception as e:
                print(f"   ❌ Failed to save model: {e}")
                raise
        else:
            print(f"\n⚠️  Model not saved - accuracy below threshold ({metrics['accuracy']:.2%} < {Config.ML_TARGET_ACCURACY:.2%})")
        
        # Log to database
        self.db.log_model_training(
            model_version=version,
            train_samples=metrics['train_samples'],
            test_samples=metrics['test_samples'],
            accuracy=metrics['accuracy'],
            precision=metrics['precision'],
            recall=metrics['recall'],
            f1=metrics['f1_score'],
            training_time=metrics['training_time'],
            deployed=deploy,
            notes=f"Accuracy: {metrics['accuracy']:.2%}"
        )
    
    def train_pipeline(self, ticker: str = None, interval: str = None, days: int = 90) -> Optional[XGBClassifier]:
        """
        Full training pipeline
        
        Args:
            ticker: Trading symbol (None = all symbols)
            interval: Timeframe (None = all timeframes)
            days: Number of days to train on
            
        Returns:
            Trained model if successful
        """
        print(f"\n{'='*70}")
        print(f"  🤖 XGBOOST TRAINING PIPELINE")
        print(f"{'='*70}\n")
        
        # Load data
        df = self.load_training_data(ticker, interval, days)
        
        if df is None or df.empty:
            print(f"❌ No training data available")
            return None
        
        # Prepare features
        X, y = self.prepare_features(df)
        
        if len(X) < 100:
            print(f"❌ Insufficient samples for training: {len(X)}")
            return None
        
        # Train model
        model, metrics = self.train_model(X, y)
        
        # Check if meets deployment threshold
        accuracy = metrics['accuracy']
        threshold = Config.ML_TARGET_ACCURACY
        
        deploy = accuracy >= threshold
        
        if deploy:
            print(f"\n✅ Model meets deployment threshold ({accuracy:.2%} >= {threshold:.2%})")
        else:
            print(f"\n⚠️  Model below deployment threshold ({accuracy:.2%} < {threshold:.2%})")
            print(f"    Model saved to shadow but NOT deployed")
        
        # Save model
        self.save_model(model, metrics, deploy=deploy)
        
        print(f"\n{'='*70}")
        print(f"  ✅ TRAINING COMPLETE")
        print(f"{'='*70}\n")
        
        return model


def main():
    """Test XGBoost trainer"""
    trainer = XGBTrainer()
    
    # Train model on all data (all symbols, all intervals, 90 days)
    model = trainer.train_pipeline(ticker=None, interval='1h', days=90)
    
    if model:
        print(f"\n✅ Model trained successfully")
    else:
        print(f"\n❌ Model training failed")


if __name__ == '__main__':
    main()
