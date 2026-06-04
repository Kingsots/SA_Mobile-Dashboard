"""
XGBoost Signal Generation Engine
ML-based signal generation using trained model
"""

# ============================================================================
# SYSTEM RULE - CORE FILE PROTECTION
# ============================================================================
# This file is CRITICAL INFRASTRUCTURE and must NEVER be replaced.
# Only patch/modify existing logic.
#
# Replacing this file causes:
#   - Signal pipeline to fail
#   - Strategy evaluation to break
#   - Silent complete trading halt
#
# Recovery: Always use git to restore or patch existing logic
# ============================================================================

import pandas as pd
import numpy as np
import joblib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.config import Config
from core.database import DatabaseManager
from features.engine import FeatureEngine

# Configure signal debug logger
signal_logger = logging.getLogger('signal_debug')
signal_logger.setLevel(logging.INFO)
signal_handler = logging.FileHandler('logs/signal_debug.log')
signal_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
signal_logger.addHandler(signal_handler)


class XGBSignalEngine:
    """
    Generate trading signals using trained XGBoost model
    
    Pipeline:
    1. Load current model (model_current.pkl)
    2. Get latest features for each ticker
    3. Run inference
    4. Map predictions to BUY/SELL/NEUTRAL
    5. Log signals with feature snapshot
    """
    
    def __init__(self):
        self.db = DatabaseManager()
        self.feature_engine = FeatureEngine()
        self.model = None
        self.model_version = None
        self.model_metadata = None
        self.load_model()
    
    def load_model(self) -> bool:
        """
        Load current deployed model
        
        Returns:
            True if model loaded successfully
        """
        model_path = Config.MODEL_CURRENT_PATH
        
        if not model_path.exists():
            print(f"⚠️  No deployed model found at {model_path}")
            return False
        
        try:
            self.model = joblib.load(model_path)
            
            # Load metadata
            metadata_path = Config.MODEL_METADATA_PATH
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    self.model_metadata = json.load(f)
                    self.model_version = self.model_metadata.get('version', 'unknown')
            
            print(f"✅ Model loaded: {self.model_version}")
            print(f"   Accuracy: {self.model_metadata['metrics']['accuracy']:.2%}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            return False
    
    def get_latest_features(self, ticker: str, interval: str, lookback: int = 1) -> Optional[pd.DataFrame]:
        """
        Get latest features for inference
        
        Args:
            ticker: Trading symbol
            interval: Timeframe
            lookback: Number of recent candles to get
            
        Returns:
            DataFrame with latest features
        """
        # Try to load from database first
        df_features = self.db.load_features(ticker, interval, days=7)
        
        if df_features is None or df_features.empty:
            # Generate fresh features
            df_features = self.feature_engine.generate_features_for_ticker(ticker, interval, days=30)
            
            if df_features is not None:
                # Save to database
                self.feature_engine.save_features_to_db(ticker, interval, df_features)
        
        if df_features is None or df_features.empty:
            return None
        
        # Get latest rows
        df_latest = df_features.tail(lookback)
        
        return df_latest
    
    def predict_signal(self, features: pd.DataFrame) -> Tuple[int, float]:
        """
        Run inference on features with robust error handling
        
        Args:
            features: DataFrame with feature values
            
        Returns:
            (signal, confidence) tuple
            signal: 1=BUY, -1=SELL, 0=NEUTRAL
            confidence: prediction probability
        """
        if self.model is None:
            return 0, 0.0
        
        # Feature columns expected by model
        feature_cols = [
            'open', 'high', 'low', 'close', 'volume',
            'ema_21', 'ema_100', 'rsi_14',
            'obv', 'ad', 'vwap', 'vwap_slope',
            'volume_sma_20', 'volume_ratio'
        ]
        
        # Filter to available columns
        available_cols = [col for col in feature_cols if col in features.columns]
        X = features[available_cols].copy()
        
        # Skip if features contain NaN
        if X.isna().any().any():
            print(f"   ⚠️  Features contain NaN - returning NEUTRAL")
            return 0, 0.0
        
        # Skip if features are empty
        if X.empty or len(X) == 0:
            print(f"   ⚠️  Empty features - returning NEUTRAL")
            return 0, 0.0
        
        try:
            # Predict with error handling
            prediction_mapped = self.model.predict(X)[0]  # Get first prediction
            prediction_proba = self.model.predict_proba(X)[0]  # Get probabilities
            
            # Map back to original labels
            # Binary model outputs: 0=SELL, 1=BUY
            reverse_label_map = {0: -1, 1: 1}
            signal = reverse_label_map.get(prediction_mapped, 0)
            
            # Confidence = max probability
            confidence = float(prediction_proba.max())
            
            return signal, confidence
            
        except Exception as e:
            print(f"   ❌ Prediction error: {e}")
            return 0, 0.0
    
    def calculate_trade_levels(self, ticker: str, signal: int, features: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate entry price, stop loss, and take profit levels for a signal
        
        Args:
            ticker: Trading symbol
            signal: 1=BUY, -1=SELL, 0=NEUTRAL
            features: Latest feature data
            
        Returns:
            Dict with entry_price, stop_loss, take_profit
        """
        if signal == 0 or features.empty:
            return {'entry_price': None, 'stop_loss': None, 'take_profit': None}
        
        latest_data = features.iloc[-1]
        current_price = float(latest_data['close'])
        atr_proxy = abs(float(latest_data['high']) - float(latest_data['low']))  # Simple ATR proxy
        
        # Risk management parameters
        risk_reward_ratio = 2.0  # 1:2 risk/reward
        risk_percentage = 0.02   # 2% risk per trade
        
        if signal == 1:  # BUY signal
            entry_price = current_price
            stop_loss = current_price - (atr_proxy * 1.5)  # 1.5x ATR below entry
            take_profit = current_price + (atr_proxy * 1.5 * risk_reward_ratio)  # 2:1 R/R
        else:  # SELL signal
            entry_price = current_price
            stop_loss = current_price + (atr_proxy * 1.5)  # 1.5x ATR above entry
            take_profit = current_price - (atr_proxy * 1.5 * risk_reward_ratio)  # 2:1 R/R
        
        return {
            'entry_price': round(entry_price, 5),
            'stop_loss': round(stop_loss, 5),
            'take_profit': round(take_profit, 5)
        }

    def generate_signal(self, ticker: str, interval: str) -> Optional[Dict]:
        """
        Generate signal for a single ticker
        
        Args:
            ticker: Trading symbol
            interval: Timeframe
            
        Returns:
            Signal dict with ticker, signal, confidence, features
        """
        # Get latest features
        df_features = self.get_latest_features(ticker, interval, lookback=1)
        
        if df_features is None or df_features.empty:
            return None
        
        # Predict signal
        signal, confidence = self.predict_signal(df_features)
        
        # Get timestamp
        timestamp = df_features.index[-1]
        
        # Check confidence threshold
        if confidence < Config.ML_SIGNAL_CONFIDENCE_MIN:
            signal = 0  # Force NEUTRAL if confidence too low
        
        # Calculate trade levels
        trade_levels = self.calculate_trade_levels(ticker, signal, df_features)
        
        # Build feature snapshot
        features_snapshot = df_features.iloc[-1].to_dict()
        features_snapshot = {k: float(v) if pd.notna(v) else None for k, v in features_snapshot.items()}
        
        # Build signal dict
        signal_data = {
            'ticker': ticker,
            'interval': interval,
            'timestamp': timestamp.isoformat(),
            'signal': signal,
            'signal_label': Config.ML_SIGNAL_LABELS[signal],
            'confidence': confidence,
            'model_version': self.model_version,
            'entry_price': trade_levels['entry_price'],
            'stop_loss': trade_levels['stop_loss'],
            'take_profit': trade_levels['take_profit'],
            'features': features_snapshot
        }
        
        return signal_data
    
    def save_signal(self, signal_data: Dict):
        """
        Save signal to database with duplicate prevention.
        Checks ml_signals table for recent signals with same ticker/interval/direction.
        
        Args:
            signal_data: Signal dictionary
            
        Returns:
            None
        """
        # ═════════════════════════════════════════════════════════════════════
        # DEDUP CHECK: Prevent signal regeneration from persistent conditions
        # ═════════════════════════════════════════════════════════════════════
        ticker = signal_data['ticker']
        interval = signal_data['interval']
        signal_direction = signal_data['signal']
        
        # Check if a recent signal of the same type exists (within 1-hour window)
        if self.db.has_recent_signal(ticker, interval, signal_direction, minutes=60):
            logging.warning(
                f"[DEDUP] SKIPPED: {ticker} {interval} {signal_direction:+d} "
                f"(recent duplicate detected in ml_signals, within 1hr window)"
            )
            return
        
        # Signal passed dedup check - save to database
        signal_id = self.db.save_ml_signal(
            ticker=signal_data['ticker'],
            timestamp=signal_data['timestamp'],
            interval=signal_data['interval'],
            signal=signal_data['signal'],
            confidence=signal_data['confidence'],
            feature_snapshot=json.dumps(signal_data['features']),
            model_version=signal_data['model_version']
        )
        if not signal_id:
            logging.error(f"[SIGNAL_SAVE_FAILED] {signal_data.get('ticker')} {signal_data.get('interval')} {signal_data.get('signal')} - save_ml_signal returned falsy")
            try:
                self.db.insert_signal_failure(
                    ticker=signal_data.get('ticker'),
                    interval=signal_data.get('interval'),
                    strategy_version=signal_data.get('model_version') or 'xgb',
                    error_message='save_ml_signal returned falsy',
                    payload=signal_data,
                )
            except Exception:
                logging.exception('Failed to log legacy XGB signal save failure')
            return False

        return signal_id
    
    def generate_signals(self, interval: str, symbols: Optional[List[str]] = None) -> List[Dict]:
        """
        Generate signals for all symbols in watchlist
        
        Args:
            interval: Timeframe to generate signals for
            symbols: List of symbols (default: all watchlist)
            
        Returns:
            List of signal dictionaries
        """
        if symbols is None:
            symbols = Config.get_symbol_list()
        
        if self.model is None:
            print(f"❌ No model loaded - cannot generate signals")
            signal_logger.error(f"No model loaded - signal generation aborted")
            return []
        
        print(f"\n{'='*70}")
        print(f"  🔮 SIGNAL GENERATION - {interval}")
        print(f"  Model: {self.model_version}")
        print(f"{'='*70}\n")
        
        signal_logger.info(f"{'='*50}")
        signal_logger.info(f"SIGNAL GENERATION START - {interval}")
        signal_logger.info(f"Model: {self.model_version}")
        signal_logger.info(f"Symbols: {len(symbols)}")
        signal_logger.info(f"{'='*50}")
        
        signals = []
        
        for i, symbol in enumerate(symbols, 1):
            print(f"[{i}/{len(symbols)}] {symbol:10}", end=' ')
            
            signal_data = self.generate_signal(symbol, interval)
            
            if signal_data is not None:
                signals.append(signal_data)
                
                # Save to database
                saved_id = self.save_signal(signal_data)
                if not saved_id:
                    logging.warning(f"Legacy XGB signal save failed for {symbol} {interval}")
                
                # Log to signal_debug.log
                signal_logger.info(
                    f"{symbol:10} | {signal_data['signal_label']:8} | "
                    f"Confidence: {signal_data['confidence']:.1%} | "
                    f"Model: {signal_data['model_version']}"
                )
                
                # Print result
                signal_label = signal_data['signal_label']
                confidence = signal_data['confidence']
                
                if signal_data['signal'] == 0:
                    print(f"⚪ {signal_label:8} (conf: {confidence:.1%})")
                elif signal_data['signal'] == 1:
                    print(f"🟢 {signal_label:8} (conf: {confidence:.1%})")
                else:
                    print(f"🔴 {signal_label:8} (conf: {confidence:.1%})")
            else:
                print(f"⚠️  No data")
                signal_logger.warning(f"{symbol:10} | NO DATA")
        
        # Summary
        buy_count = sum(1 for s in signals if s['signal'] == 1)
        sell_count = sum(1 for s in signals if s['signal'] == -1)
        neutral_count = sum(1 for s in signals if s['signal'] == 0)
        
        print(f"\n{'='*70}")
        print(f"  ✅ SIGNALS GENERATED: {len(signals)}/{len(symbols)}")
        print(f"{'='*70}")
        print(f"  🟢 BUY:     {buy_count:3}")
        print(f"  🔴 SELL:    {sell_count:3}")
        print(f"  ⚪ NEUTRAL: {neutral_count:3}")
        print(f"{'='*70}\n")
        
        signal_logger.info(f"SUMMARY: {len(signals)} signals generated")
        signal_logger.info(f"BUY: {buy_count}, SELL: {sell_count}, NEUTRAL: {neutral_count}")
        signal_logger.info(f"{'='*50}\n")
        
        return signals
    
    def get_actionable_signals(self, signals: List[Dict]) -> List[Dict]:
        """
        Filter signals to only actionable ones (BUY/SELL with confidence above threshold)
        
        Args:
            signals: List of all signals
            
        Returns:
            List of actionable signals
        """
        actionable = [
            s for s in signals 
            if s['signal'] != 0 and s['confidence'] >= Config.ML_SIGNAL_CONFIDENCE_MIN
        ]
        
        return actionable


def main():
    """Test signal engine"""
    engine = XGBSignalEngine()
    
    # Generate signals for 1h timeframe
    signals = engine.generate_signals('1h', symbols=['EURUSD', 'GBPUSD', 'USDJPY'])
    
    # Get actionable signals
    actionable = engine.get_actionable_signals(signals)
    
    print(f"\n📊 Actionable Signals: {len(actionable)}")
    for signal in actionable:
        print(f"   {signal['ticker']:10} {signal['signal_label']:8} (conf: {signal['confidence']:.1%})")


if __name__ == '__main__':
    main()
