"""
XGBoost Signal Generation Engine
ML-based signal generation using trained model
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd

from core.config import Config
from core.database import DatabaseManager
from features.engine import FeatureEngine
from signals.event_filter import MarketEvent
from alerts.telegram_bot import TelegramBot


LOG_DIR = Path('logs')
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, pd.Timestamp)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    return str(value)


def _sanitize_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not metadata:
        return {}
    return json.loads(json.dumps(metadata, default=_json_default))

# Configure signal debug logger
signal_logger = logging.getLogger('signal_debug')
signal_logger.setLevel(logging.INFO)
signal_handler = logging.FileHandler(LOG_DIR / 'signal_debug.log')
signal_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
signal_logger.addHandler(signal_handler)

event_logger = logging.getLogger('event_debug')
event_logger.setLevel(logging.INFO)
event_handler = logging.FileHandler(LOG_DIR / 'event_debug.log')
event_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
event_logger.addHandler(event_handler)


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
        self._last_event_key: Optional[str] = None
        self._last_event_result: Optional[Dict[str, Any]] = None
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

    def _event_key(self, event: MarketEvent) -> str:
        timestamp = pd.Timestamp(event.timestamp).isoformat()
        return f"{event.ticker}|{event.interval}|{event.event_type}|{timestamp}"

    def _event_payload(self, event: MarketEvent, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = event.to_dict()
        payload['id'] = self._event_key(event)
        if extra:
            payload.update(extra)
        return payload

    def _log_event_debug(self, payload: Dict[str, Any]) -> None:
        event_logger.info(json.dumps(payload, default=_json_default))
    
    def _refresh_features_if_stale(
        self,
        ticker: str,
        interval: str,
        df_features: Optional[pd.DataFrame],
        lookback_days: int,
    ) -> Optional[pd.DataFrame]:
        """Ensure we have fresh features; regenerate if stale or missing."""
        needs_regen = False

        if df_features is None or df_features.empty:
            needs_regen = True
        else:
            latest_ts = pd.Timestamp(df_features['timestamp'].iloc[-1])
            latest_dt = latest_ts.to_pydatetime()
            age_minutes = (datetime.now(timezone.utc) - latest_dt).total_seconds() / 60.0
            if age_minutes > Config.FEATURE_STALENESS_MINUTES:
                needs_regen = True

        if not needs_regen:
            return df_features

        signal_logger.warning(
            f"{ticker} {interval}: refreshing features (stale or missing data)"
        )

        refreshed = self.feature_engine.generate_features_for_ticker(
            ticker,
            interval,
            days=lookback_days,
        )

        if refreshed is not None and not refreshed.empty:
            self.feature_engine.save_features_to_db(ticker, interval, refreshed)
            return refreshed

        signal_logger.error(
            f"{ticker} {interval}: feature regeneration failed; skipping signal generation"
        )
        return None

    def get_latest_features(self, ticker: str, interval: str, lookback: int = 1) -> Optional[pd.DataFrame]:
        """
        Get latest features for inference
        
        Args:
            ticker: Trading symbol
            interval: Timeframe
            lookback: Number of recent candles to get
            
        Returns:
            DataFrame with latest features (with lookback + 1 rows to enable lag1 creation)
        """
        lookback_days = Config.FEATURE_REFRESH_LOOKBACK_DAYS

        # Try to load from database first
        df_features = self.db.load_features(ticker, interval, days=lookback_days)

        df_features = self._refresh_features_if_stale(
            ticker,
            interval,
            df_features,
            lookback_days,
        )

        if df_features is None or df_features.empty:
            return None
        
        # Get more rows than lookback so we can create lag1
        # Need lookback + 1 rows to shift and still have lookback valid rows
        tail_count = max(lookback + 1, 2)
        df_latest = df_features.tail(tail_count)
        
        return df_latest
    
    def prepare_features_for_inference(self, features: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare features for inference - ensure lag1 features are present and valid
        
        If lag1 features are missing or contain NaN values, create them by shifting base features.
        Lag1 features are needed for model inference (model trained on lagged indicators).
        """
        if features is None or features.empty:
            return features
        
        # List of base indicator columns that need lagging
        base_cols = ['ema_21', 'ema_100', 'rsi_14', 'obv', 'ad', 'vwap_slope', 'volume_sma_20', 'volume_ratio']
        
        df = features.copy()
        
        # Create/recreate lag1 features - always recreate to handle NaN stale values from DB
        for col in base_cols:
            lag_col = f'{col}_lag1'
            if col in df.columns:
                # Always recreate lag1 from base feature (handles both missing and NaN lag1 values)
                df[lag_col] = df[col].shift(1)
            else:
                logging.warning(f"Base feature column missing: {col} - cannot create lag1")
        
        # Debug: show what columns we have before returning
        logging.debug(f"After prepare_features: {df.columns.tolist()}")
        logging.debug(f"Latest row lag1 values: {df.iloc[-1][[col for col in df.columns if 'lag1' in col]].to_dict() if len(df) > 0 else 'empty'}")
        
        return df
    
    def predict_signal(self, features: pd.DataFrame) -> Tuple[int, float]:
        """
        Generate signal from features using loaded model.
        Uses model_metadata to determine which features the model expects.
        
        Args:
            features: DataFrame with calculated features
            
        Returns:
            tuple: (signal, confidence) where signal is -1/0/1
        """
        if self.model is None or self.model_metadata is None:
            logging.warning("Model or metadata not loaded")
            return 0, 0.0
        
        # Get the features the model was actually trained on
        expected_features = self.model_metadata.get('features', [])
        
        if not expected_features:
            logging.error("No features listed in model_metadata")
            return 0, 0.0
        
        # Filter to only features that exist in our dataframe
        available_cols = [col for col in expected_features if col in features.columns]
        
        # Check if we have all required features
        if len(available_cols) != len(expected_features):
            missing = set(expected_features) - set(available_cols)
            logging.warning(f"Missing {len(missing)} required features: {missing}")
            return 0, 0.0
        
        # Get the last row with only the features the model expects
        X = features[available_cols].iloc[[-1]].copy()
        
        # Check for NaN values
        if X.isna().any().any():
            missing_vals = X.columns[X.isna().any()].tolist()
            logging.warning(f"NaN values in features: {missing_vals}")
            return 0, 0.0
        
        # Make prediction
        try:
            prediction_mapped = self.model.predict(X)[0]
            
            # Use model's confidence if available, otherwise default
            confidence = self.model_metadata.get('default_confidence', 0.75)
            
            logging.info(f"Prediction: {prediction_mapped}, Confidence: {confidence}")
            return int(prediction_mapped), float(confidence)
            
        except Exception as e:
            logging.error(f"Error during prediction: {e}")
            logging.error(f"Feature columns attempted: {available_cols}")
            logging.error(f"X shape: {X.shape}, X columns: {X.columns.tolist()}")
            return 0, 0.0
    
    def calculate_trade_levels(self, ticker: str, signal: int, features: pd.DataFrame, event: Optional[Any] = None) -> Dict[str, float]:
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
        
        # Calculate ATR proxy with fallback for edge cases (e.g., gold prices)
        atr_proxy = abs(float(latest_data['high']) - float(latest_data['low']))
        
        # Fallback: if ATR is 0 or NaN, use 0.2% of price
        if atr_proxy == 0 or pd.isna(atr_proxy):
            atr_proxy = current_price * 0.002  # 0.2% fallback
        
        # Risk management parameters
        risk_reward_ratio = 2.0  # 1:2 risk/reward
        risk_percentage = 0.02   # 2% risk per trade
        
        if signal == 1:  # BUY signal
            entry_price = self.calculate_pattern_entry_price(signal, features, event)
            stop_loss = entry_price - (atr_proxy * 1.5)  # 1.5x ATR below entry
            take_profit = entry_price + (atr_proxy * 1.5 * risk_reward_ratio)  # 2:1 R/R
        else:  # SELL signal
            entry_price = self.calculate_pattern_entry_price(signal, features, event)
            stop_loss = entry_price + (atr_proxy * 1.5)  # 1.5x ATR above entry
            take_profit = entry_price - (atr_proxy * 1.5 * risk_reward_ratio)  # 2:1 R/R
        
        return {
            'entry_price': round(entry_price, 5),
            'stop_loss': round(stop_loss, 5),
            'take_profit': round(take_profit, 5)
        }

    def calculate_pattern_entry_price(
        self,
        signal: int,
        features: pd.DataFrame,
        event: Optional[Any] = None
    ) -> float:
        """
        Calculate entry price at pattern origin, not current close.
        
        Uses hybrid approach:
        - Finds where pattern started (RSI low, engulfing origin, etc.)
        - Applies minimum distance buffer to prevent entries too far back
        - Falls back to current close if pattern data unavailable
        
        Args:
            signal: 1 (BUY), -1 (SELL), 0 (NEUTRAL)
            features: DataFrame with 20-30 rows of lookback data
            event: MarketEvent object with pattern details (optional)
        
        Returns:
            Entry price (float, rounded to 5 decimals)
        """
        # Safety checks
        if signal == 0 or features.empty or len(features) < 2:
            return float(features.iloc[-1]['close'])
        
        latest = features.iloc[-1]
        lookback = features.iloc[-20:] if len(features) >= 20 else features
        current_price = float(latest['close'])
        
        # Minimum distance buffer (50 pips for major pairs)
        # Prevents entry too far back in history
        MIN_ENTRY_DISTANCE = 0.0050
        
        if signal == 1:  # BUY
            minimum_entry = current_price - MIN_ENTRY_DISTANCE
        else:  # SELL
            minimum_entry = current_price + MIN_ENTRY_DISTANCE
        
        # If no event data, use current close (fallback)
        if event is None:
            return round(current_price, 5)
        
        event_type = str(event.event_type).lower() if hasattr(event, 'event_type') else ''
        pattern_entry = None
        
        try:
            # ===== RSI REBOUND EVENTS =====
            if 'rsi_rebound' in event_type or 'rsi' in event_type:
                if 'bullish' in event_type or signal == 1:
                    # Entry at RSI LOW (where reversal started)
                    rsi_min_idx = lookback['rsi_14'].idxmin()
                    pattern_entry = float(lookback.loc[rsi_min_idx, 'low'])
                else:  # bearish
                    # Entry at RSI HIGH (where reversal started)
                    rsi_max_idx = lookback['rsi_14'].idxmax()
                    pattern_entry = float(lookback.loc[rsi_max_idx, 'high'])
            
            # ===== ENGULFING STRUCTURE EVENTS =====
            elif 'engulf' in event_type:
                if len(features) >= 2:
                    prev_candle = features.iloc[-2]
                    if 'bullish' in event_type or signal == 1:
                        # Entry at previous candle LOW (support level)
                        pattern_entry = float(prev_candle['low'])
                    else:  # bearish
                        # Entry at previous candle HIGH (resistance level)
                        pattern_entry = float(prev_candle['high'])
            
            # ===== EMA CROSSOVER EVENTS =====
            elif 'ema' in event_type or 'crossover' in event_type or 'cross' in event_type:
                if 'bullish' in event_type or signal == 1:
                    # Entry at LOW of crossing candle
                    pattern_entry = float(latest['low'])
                else:
                    # Entry at HIGH of crossing candle
                    pattern_entry = float(latest['high'])
            
            # ===== VOLUME/VOLATILITY EVENTS =====
            elif 'volume' in event_type or 'volatility' in event_type or 'atr' in event_type:
                if 'bullish' in event_type or signal == 1:
                    # Entry at LOW of current candle (volume spike point)
                    pattern_entry = float(latest['low'])
                else:
                    # Entry at HIGH of current candle (volume spike point)
                    pattern_entry = float(latest['high'])
            
            # ===== VWAP CROSS EVENTS =====
            elif 'vwap' in event_type:
                if 'bullish' in event_type or signal == 1:
                    pattern_entry = float(latest['low'])
                else:
                    pattern_entry = float(latest['high'])
            
            # ===== DEFAULT FALLBACK =====
            else:
                pattern_entry = current_price
            
        except Exception as e:
            logging.warning(f"Pattern entry calculation error: {e}, using current price")
            pattern_entry = current_price
        
        # Safety: If pattern_entry is None or invalid, use current
        if pattern_entry is None or pd.isna(pattern_entry):
            return round(current_price, 5)
        
        # ===== HYBRID APPROACH: Apply minimum distance buffer =====
        if signal == 1:  # BUY
            # Entry shouldn't be TOO far below current (prevents ancient entries)
            entry_price = max(pattern_entry, minimum_entry)
        else:  # SELL
            # Entry shouldn't be TOO far above current
            entry_price = min(pattern_entry, minimum_entry)
        
        return round(float(entry_price), 5)

    def generate_signal(
        self,
        ticker: str,
        interval: str,
        *,
        event: Optional[MarketEvent] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate a signal optionally annotated with event metadata."""

        trigger_metadata = _sanitize_metadata(metadata)

        df_features = self.get_latest_features(ticker, interval, lookback=30)
        if df_features is None or df_features.empty:
            if event is not None:
                self._log_event_debug(
                    {
                        'phase': 'event_no_features',
                        'event': self._event_payload(event),
                        'trigger_metadata': trigger_metadata,
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                    }
                )
            return None

        # Prepare lag1 features before inference
        df_features_prepared = self.prepare_features_for_inference(df_features)
        signal, confidence = self.predict_signal(df_features_prepared)

        if 'timestamp' in df_features.columns:
            timestamp = df_features['timestamp'].iloc[-1]
        else:
            timestamp = df_features.index[-1]

        feature_dt = pd.Timestamp(timestamp).to_pydatetime()
        feature_age_min = (datetime.now(timezone.utc) - feature_dt).total_seconds() / 60.0

        # Don't zero out signal based on confidence - let model output flow through
        # Events with detected patterns will have signal, confidence represents ML certainty
        # Telegram alerts will use raw confidence without filtering

        trade_levels = self.calculate_trade_levels(ticker, signal, df_features, event)

        # ONLY include numeric feature columns in the snapshot (exclude metadata like ticker, interval, timestamp, created_at)
        feature_col_names = [
            'open', 'high', 'low', 'close', 'volume',
            'ema_21', 'ema_100', 'rsi_14',
            'obv', 'ad', 'vwap', 'vwap_slope',
            'volume_sma_20', 'volume_ratio'
        ]
        
        features_snapshot: Dict[str, Any] = {}
        for col in feature_col_names:
            if col in df_features.columns:
                value = df_features[col].iloc[-1]
                if pd.isna(value):
                    features_snapshot[col] = None
                elif isinstance(value, np.generic):
                    features_snapshot[col] = value.item()
                else:
                    try:
                        features_snapshot[col] = float(value)
                    except (ValueError, TypeError):
                        features_snapshot[col] = None
        
        # Convert all values to float for JSON serialization
        clean_snapshot = {
            k: (float(v) if v is not None else None)
            for k, v in features_snapshot.items()
        }

        signal_data: Dict[str, Any] = {
            'ticker': ticker,
            'interval': interval,
            'timestamp': pd.Timestamp(timestamp).isoformat(),
            'feature_timestamp': pd.Timestamp(timestamp).isoformat(),
            'feature_age_minutes': round(feature_age_min, 2),
            'signal': signal,
            'signal_label': Config.ML_SIGNAL_LABELS[signal],
            'confidence': confidence,
            'model_version': self.model_version,
            'entry_price': trade_levels['entry_price'],
            'stop_loss': trade_levels['stop_loss'],
            'take_profit': trade_levels['take_profit'],
            'features': clean_snapshot,  # Use sanitized snapshot instead of raw features_snapshot
        }

        # USE EVENT CONFIDENCE - For event-driven signals, use the event's confidence
        # because it represents the pattern reliability from the detector, which is more
        # meaningful than the model's confidence (which is 0.0% for neutral model outputs).
        # Apply this ALWAYS for event-driven signals, even if model returns NEUTRAL,
        # since the event pattern has real signal confidence.
        if event is not None:  # Apply for any event-driven signal
            event_confidence = getattr(event, 'confidence', None)
            if event_confidence is not None:
                signal_data['confidence'] = float(event_confidence)

        trigger_context: Dict[str, Any] = {
            'type': 'event' if event is not None else 'schedule',
            'metadata': trigger_metadata,
        }
        if event is not None:
            event_payload = self._event_payload(event)
            trigger_context['event_id'] = event_payload['id']
            trigger_context['event'] = event_payload
            self._last_event_key = event_payload['id']
            self._last_event_result = signal_data
            self._log_event_debug(
                {
                    'phase': 'event_signal_generated',
                    'event': event_payload,
                    'trigger_metadata': trigger_metadata,
                    'signal': {
                        'signal': signal,
                        'confidence': confidence,
                        'entry_price': trade_levels['entry_price'],
                        'stop_loss': trade_levels['stop_loss'],
                        'take_profit': trade_levels['take_profit'],
                        'timestamp': signal_data['timestamp'],
                    },
                }
            )

        signal_data['trigger_context'] = trigger_context
        if event is not None:
            signal_data['triggered_by'] = f"event:{event.event_type}"
        else:
            signal_data['triggered_by'] = 'time'

        return signal_data
    
    def save_signal(self, signal_data: Dict[str, Any]) -> None:
        """
        Save signal to database
        
        Args:
            signal_data: Signal dictionary
        """
        trigger_source = signal_data.get('triggered_by') or 'time'
        
        # Determine strategy version from source
        source = signal_data.get('source', 'strategy_core_v1')
        strategy_version = 'v2' if 'v2' in source.lower() else 'v1'
        
        self.db.save_ml_signal(
            ticker=signal_data['ticker'],
            timestamp=signal_data['timestamp'],
            interval=signal_data['interval'],
            signal=signal_data['signal'],
            confidence=signal_data['confidence'],
            feature_snapshot=json.dumps(signal_data['features'], default=_json_default),
            model_version=signal_data['model_version'],
            triggered_by=trigger_source,
            strategy_version=strategy_version,
        )
    
    def generate_signals(
        self,
        interval: str,
        symbols: Optional[List[str]] = None,
        *,
        trigger_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate signals for all symbols in watchlist
        
        Args:
            interval: Timeframe to generate signals for
            symbols: List of symbols (default: all watchlist)
            trigger_metadata: Optional metadata describing the trigger context
            
        Returns:
            List of signal dictionaries
        """
        if symbols is None:
            symbols = Config.get_symbol_list()
        
        if self.model is None:
            print(f"❌ No model loaded - cannot generate signals")
            signal_logger.error(f"No model loaded - signal generation aborted")
            return []
        
        run_metadata = _sanitize_metadata(trigger_metadata)
        self._log_event_debug(
            {
                'phase': 'schedule_run_start',
                'interval': interval,
                'symbols': symbols,
                'trigger_metadata': run_metadata,
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }
        )

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

            symbol_metadata = dict(run_metadata)
            symbol_metadata.update({'symbol_index': i, 'symbol_total': len(symbols)})

            signal_data = self.generate_signal(
                symbol,
                interval,
                metadata=symbol_metadata,
            )
            
            if signal_data is not None:
                signals.append(signal_data)
                
                # Save to database
                self.save_signal(signal_data)
                
                # Log to signal_debug.log
                signal_logger.info(
                    f"{symbol:10} | {signal_data['signal_label']:8} | "
                    f"Confidence: {signal_data['confidence']:.1%} | "
                    f"Model: {signal_data['model_version']} | "
                    f"Feature Age: {signal_data['feature_age_minutes']:.1f}m"
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

        self._log_event_debug(
            {
                'phase': 'schedule_run_summary',
                'interval': interval,
                'counts': {
                    'total': len(signals),
                    'buy': buy_count,
                    'sell': sell_count,
                    'neutral': neutral_count,
                },
                'symbols': symbols,
                'trigger_metadata': run_metadata,
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }
        )
        
        return signals

    def handle_event(
        self,
        event: MarketEvent,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        persist: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Process a MarketEvent and optionally persist the resulting signal."""

        sanitized_metadata = _sanitize_metadata(metadata)
        event_payload = self._event_payload(event)

        self._log_event_debug(
            {
                'phase': 'event_received',
                'event': event_payload,
                'trigger_metadata': sanitized_metadata,
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }
        )

        signal_data = self.generate_signal(
            event.ticker,
            event.interval,
            event=event,
            metadata=sanitized_metadata,
        )

        if signal_data is None:
            self._log_event_debug(
                {
                    'phase': 'event_no_signal',
                    'event': event_payload,
                    'trigger_metadata': sanitized_metadata,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                }
            )
            return None

        signal_summary = {
            'ticker': signal_data['ticker'],
            'signal': signal_data['signal'],
            'signal_label': signal_data['signal_label'],
            'confidence': signal_data['confidence'],
            'model_version': signal_data['model_version'],
            'timestamp': signal_data['timestamp'],
        }

        if persist:
            self.save_signal(signal_data)
            self._log_event_debug(
                {
                    'phase': 'event_signal_persisted',
                    'event': event_payload,
                    'trigger_metadata': sanitized_metadata,
                    'signal': signal_summary,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                }
            )
        else:
            self._log_event_debug(
                {
                    'phase': 'event_signal_generated',
                    'event': event_payload,
                    'trigger_metadata': sanitized_metadata,
                    'signal': signal_summary,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                }
            )

        return signal_data
    
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
