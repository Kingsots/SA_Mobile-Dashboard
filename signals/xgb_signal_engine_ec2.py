"""
Pure Strategy Core Signal Generation Engine
Event-driven, dual-strategy (v1 + v2) concurrent execution
No ML model dependencies
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from core.config import Config
from core.database import DatabaseManager
from core.pipeline_tracker import get_tracker
from signals.event_filter import MarketEvent
from alerts.telegram_bot import TelegramBot

# ═══════════════════════════════════════════════════════════════════════════
# PURE STRATEGY ENGINE - DUAL CONCURRENT STRATEGIES
# ═══════════════════════════════════════════════════════════════════════════
# Import both strategies for concurrent execution
try:
    from core.strategy_core_v1 import evaluate as evaluate_v1
    STRATEGY_V1_AVAILABLE = True
except Exception as e:
    STRATEGY_V1_AVAILABLE = False
    evaluate_v1 = None
    logging.error(f"Failed to import strategy_core_v1: {e}")

try:
    from core.strategy_core_v2 import evaluate as evaluate_v2
    STRATEGY_V2_AVAILABLE = True
except Exception as e:
    STRATEGY_V2_AVAILABLE = False
    evaluate_v2 = None
    logging.error(f"Failed to import strategy_core_v2: {e}")


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

# Pure engine mode - no ML references
DEBUG_MODE = False

event_logger = logging.getLogger('event_debug')
event_logger.setLevel(logging.INFO)
event_handler = logging.FileHandler(LOG_DIR / 'event_debug.log')
event_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
event_logger.addHandler(event_handler)


class PureStrategyEngine:
    """
    Generate trading signals using pure strategy core (deterministic, no ML)
    
    Runs V1 and V2 concurrently:
    - V1: 5-condition AND gate (baseline reference)
    - V2: RSI Break & Retest with stateful tracking
    
    Pipeline:
    1. For each ticker-interval pair
    2. Load OHLCV data once
    3. Run through strategy_core_v1 → returns signal
    4. Run through strategy_core_v2 → returns signal
    5. Persist both signals with clear [V1] and [V2] tags
    6. Load/save V2 state for persistence
    """
    
    # HARD DATA GATE: Minimum rows needed for proper indicator computation
    # EMA_100 requires 100 bars + RSI requires 15 = 120 minimum
    MIN_DATA_ROWS = 120
    
    def __init__(self):
        self.db = DatabaseManager()
        self._last_event_key: Optional[str] = None
        self._last_event_result: Optional[Dict[str, Any]] = None
        self.model = None  # Backward compatibility - pure strategy has no ML model
        
        print("\n" + "="*70)
        print("✅ Pure Strategy Engine Initialized")
        print(f"   V1 Available: {STRATEGY_V1_AVAILABLE}")
        print(f"   V2 Available: {STRATEGY_V2_AVAILABLE}")
        print("="*70 + "\n")
    
    def load_model(self):
        """Backward compatibility - pure strategy needs no model loading"""
        pass

    def get_latest_ohlcv(self, ticker: str, interval: str, lookback: int = 500) -> Optional[pd.DataFrame]:
        """
        Load latest OHLCV data for strategy evaluation.
        
        Args:
            ticker: Symbol to load
            interval: Timeframe ('30m', '1h', '4h', etc.)
            lookback: Number of bars to load (default 500)
            
        Returns:
            DataFrame with columns [open, high, low, close, volume] indexed by datetime
        """
        try:
            df = self.db.load_ohlcv_data(ticker, interval, limit=lookback)
            if df is None or len(df) < self.MIN_DATA_ROWS:
                return None
            return df
        except Exception as e:
            logging.warning(f"Failed to load OHLCV {ticker}-{interval}: {e}")
            return None

    def _event_key(self, event: MarketEvent) -> str:
        timestamp = pd.Timestamp(event.timestamp).isoformat()
        return f"{event.ticker}|{event.interval}|{event.event_type}|{timestamp}"

    def _event_payload(self, event: MarketEvent, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = event.to_dict() if hasattr(event, 'to_dict') else {}
        payload['id'] = self._event_key(event) if event else "unknown"
        if extra:
            payload.update(extra)
        return payload

    def _log_event_debug(self, payload: Dict[str, Any]) -> None:
        event_logger.info(json.dumps(payload, default=_json_default))

    def generate_signal(
        self,
        ticker: str,
        interval: str,
        strategy_name: str,
        *,
        event: Optional[MarketEvent] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a signal using specified strategy (v1 or v2).
        
        Args:
            ticker: Symbol to evaluate
            interval: Timeframe
            strategy_name: 'strategy_core_v1' or 'strategy_core_v2'
            event: Optional market event that triggered evaluation
            metadata: Optional metadata
            
        Returns:
            Signal dict if exit conditions met, else None
        """
        trigger_metadata = _sanitize_metadata(metadata)
        
        # Select appropriate evaluator
        if strategy_name == 'strategy_core_v1':
            if not STRATEGY_V1_AVAILABLE:
                logging.error(f"Strategy V1 not available for {ticker}-{interval}")
                return None
            evaluator = evaluate_v1
        elif strategy_name == 'strategy_core_v2':
            if not STRATEGY_V2_AVAILABLE:
                logging.error(f"Strategy V2 not available for {ticker}-{interval}")
                return None
            evaluator = evaluate_v2
        else:
            logging.error(f"Unknown strategy: {strategy_name}")
            return None
        
        # Load OHLCV data
        df_ohlcv = self.get_latest_ohlcv(ticker, interval)
        
        # Silent filter - insufficient data
        if df_ohlcv is None or len(df_ohlcv) < self.MIN_DATA_ROWS:
            if event is not None:
                self._log_event_debug({
                    'phase': 'event_no_data',
                    'strategy': strategy_name,
                    'event': self._event_payload(event),
                    'trigger_metadata': trigger_metadata,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                })
            return None
        
        # Evaluate strategy
        core_signal = None
        try:
            core_signal = evaluator(ticker, interval, df_ohlcv, min_rows=2)
        except Exception as e:
            logging.warning(f"Strategy {strategy_name} evaluation error for {ticker}: {e}")
            return None
        
        # Silent filter - no signal (neutral)
        if core_signal is None or core_signal == 0:
            return None
        
        # Extract timestamp
        if 'timestamp' in df_ohlcv.columns:
            timestamp = df_ohlcv['timestamp'].iloc[-1]
        else:
            timestamp = df_ohlcv.index[-1]
        
        feature_dt = pd.Timestamp(timestamp).to_pydatetime()
        feature_age_min = (datetime.now(timezone.utc) - feature_dt).total_seconds() / 60.0
        
        # NOTE: Entry/SL/TP calculation moved to V2 execution engine
        # V1 returns pure direction signal only
        
        # Build feature snapshot
        feature_col_names = [
            'open', 'high', 'low', 'close', 'volume',
            'ema_21', 'ema_100', 'rsi_14',
            'obv', 'ad', 'vwap', 'vwap_slope',
            'volume_sma_20', 'volume_ratio'
        ]
        
        features_snapshot: Dict[str, Any] = {}
        for col in feature_col_names:
            if col in df_ohlcv.columns:
                value = df_ohlcv[col].iloc[-1]
                if pd.isna(value):
                    features_snapshot[col] = None
                elif isinstance(value, np.generic):
                    features_snapshot[col] = value.item()
                else:
                    try:
                        features_snapshot[col] = float(value)
                    except (ValueError, TypeError):
                        features_snapshot[col] = None
        
        clean_snapshot = {
            k: (float(v) if v is not None else None)
            for k, v in features_snapshot.items()
        }
        
        # Build signal data (V1: direction only, no execution prices)
        signal_data: Dict[str, Any] = {
            'ticker': ticker,
            'interval': interval,
            'timestamp': pd.Timestamp(timestamp).isoformat(),
            'feature_timestamp': pd.Timestamp(timestamp).isoformat(),
            'feature_age_minutes': round(feature_age_min, 2),
            'signal': core_signal,
            'signal_label': Config.ML_SIGNAL_LABELS[core_signal],
            'confidence': 1.0,  # Pure strategy = deterministic
            'source': strategy_name,
            'model_version': strategy_name,
            'v1_only': True,  # Indicates V1 output without execution prices
            'features': clean_snapshot,
        }
        
        # Log event signal generation
        if event is not None:
            event_payload = self._event_payload(event)
            self._log_event_debug({
                'phase': 'event_signal_generated',
                'strategy': strategy_name,
                'event': event_payload,
                'trigger_metadata': trigger_metadata,
                'signal': {
                    'signal': core_signal,
                    'confidence': 1.0,
                    'timestamp': signal_data['timestamp'],
                    'note': 'Entry/SL/TP calculated by V2 execution engine in real-time',
                },
            })
            self._last_event_key = event_payload['id']
            self._last_event_result = signal_data
        
        # Trigger context
        trigger_context: Dict[str, Any] = {
            'type': 'event' if event is not None else 'schedule',
            'metadata': trigger_metadata,
        }
        if event is not None:
            event_payload = self._event_payload(event)
            trigger_context['event_id'] = event_payload['id']
            trigger_context['event'] = event_payload
            signal_data['triggered_by'] = f"event:{event.event_type}"
        else:
            signal_data['triggered_by'] = 'schedule'
        
        signal_data['trigger_context'] = trigger_context
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
        Generate signals for all symbols using both V1 and V2 strategies (concurrent).
        
        Args:
            interval: Timeframe to generate signals for
            symbols: List of symbols (default: all watchlist)
            trigger_metadata: Optional metadata describing the trigger context
            
        Returns:
            List of signal dictionaries from both strategies
            
        PIPELINE:
        For each symbol:
            - Load OHLCV once
            - Run V1 evaluate() → save signal if triggered
            - Run V2 evaluate() → save signal if triggered
        """
        if symbols is None:
            symbols = Config.get_symbol_list()
        
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
        print(f"  🔮 DUAL STRATEGY SIGNAL GENERATION - {interval}")
        print(f"  V1 Available: {STRATEGY_V1_AVAILABLE}")
        print(f"  V2 Available: {STRATEGY_V2_AVAILABLE}")
        print(f"{'='*70}\n")
        
        signal_logger.info(f"{'='*50}")
        signal_logger.info(f"SIGNAL GENERATION START - {interval}")
        signal_logger.info(f"Strategies: V1={STRATEGY_V1_AVAILABLE}, V2={STRATEGY_V2_AVAILABLE}")
        signal_logger.info(f"Symbols: {len(symbols)}")
        signal_logger.info(f"{'='*50}")
        
        signals = []
        
        # Loop through each symbol
        for i, symbol in enumerate(symbols, 1):
            print(f"[{i}/{len(symbols)}] {symbol:10}", end=' ')

            symbol_metadata = dict(run_metadata)
            symbol_metadata.update({'symbol_index': i, 'symbol_total': len(symbols)})

            # Generate signals from BOTH strategies
            symbol_signals = []
            strategies = []
            
            if STRATEGY_V1_AVAILABLE:
                signal_v1 = self.generate_signal(
                    symbol,
                    interval,
                    'strategy_core_v1',
                    metadata=symbol_metadata,
                )
                if signal_v1 is not None:
                    symbol_signals.append(signal_v1)
                    strategies.append('V1')
                    
                    # Save to database
                    if signal_v1['signal'] != 0:
                        self.save_signal(signal_v1)
                        
                        # Track V1 persistence in pipeline
                        try:
                            signal_id = f"{signal_v1['ticker']}|{interval}|{signal_v1['timestamp']}|v1"
                            get_tracker().mark_persisted(signal_id=signal_id)
                        except Exception:
                            pass  # Never let tracker crash signal flow
                        
                        # Log to signal_debug.log
                        signal_logger.info(
                            f"{symbol:10} | [V1] {signal_v1['signal_label']:8} | "
                            f"Confidence: {signal_v1['confidence']:.1%}"
                        )
            
            if STRATEGY_V2_AVAILABLE:
                signal_v2 = self.generate_signal(
                    symbol,
                    interval,
                    'strategy_core_v2',
                    metadata=symbol_metadata,
                )
                if signal_v2 is not None:
                    symbol_signals.append(signal_v2)
                    strategies.append('V2')
                    
                    # Save to database
                    if signal_v2['signal'] != 0:
                        self.save_signal(signal_v2)
                        
                        # Track V2 persistence in pipeline
                        try:
                            signal_id = f"{signal_v2['ticker']}|{interval}|{signal_v2['timestamp']}|v2"
                            get_tracker().mark_persisted(signal_id=signal_id)
                        except Exception:
                            pass  # Never let tracker crash signal flow
                        
                        # Log to signal_debug.log
                        entry_data = ""
                        if signal_v2.get('entry_price') is not None:
                            entry_data = f" | Entry: {signal_v2['entry_price']:.5f} | SL: {signal_v2['stop_loss']:.5f} | TP: {signal_v2['take_profit']:.5f}"
                        signal_logger.info(
                            f"{symbol:10} | [V2] {signal_v2['signal_label']:8} | "
                            f"Confidence: {signal_v2['confidence']:.1%}{entry_data}"
                        )
            
            signals.extend(symbol_signals)
            
            # Print result
            if symbol_signals:
                strategy_tags = '+'.join(strategies)
                signal_labels = [s['signal_label'] for s in symbol_signals]
                print(f"[{strategy_tags:6}] {' / '.join(signal_labels)}")
            else:
                print(f"⚠️  No signals")
                signal_logger.debug(f"{symbol:10} | NO SIGNALS FROM ANY STRATEGY")
        
        # Summary
        v1_buy = sum(1 for s in signals if s.get('source') == 'strategy_core_v1' and s['signal'] == 1)
        v1_sell = sum(1 for s in signals if s.get('source') == 'strategy_core_v1' and s['signal'] == -1)
        v2_buy = sum(1 for s in signals if s.get('source') == 'strategy_core_v2' and s['signal'] == 1)
        v2_sell = sum(1 for s in signals if s.get('source') == 'strategy_core_v2' and s['signal'] == -1)
        
        print(f"\n{'='*70}")
        print(f"  ✅ SIGNALS GENERATED: {len(signals)} total")
        print(f"{'='*70}")
        print(f"  [V1] 🟢 BUY:  {v1_buy:3}  |  🔴 SELL: {v1_sell:3}")
        print(f"  [V2] 🟢 BUY:  {v2_buy:3}  |  🔴 SELL: {v2_sell:3}")
        print(f"{'='*70}\n")
        
        signal_logger.info(f"SUMMARY: {len(signals)} total signals")
        signal_logger.info(f"V1: BUY={v1_buy}, SELL={v1_sell}")
        signal_logger.info(f"V2: BUY={v2_buy}, SELL={v2_sell}")
        signal_logger.info(f"{'='*50}\n")

        self._log_event_debug(
            {
                'phase': 'schedule_run_summary',
                'interval': interval,
                'counts': {
                    'total': len(signals),
                    'v1_buy': v1_buy,
                    'v1_sell': v1_sell,
                    'v2_buy': v2_buy,
                    'v2_sell': v2_sell,
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
    ) -> List[Dict[str, Any]]:
        """
        Process a MarketEvent and generate signals from both V1 and V2.
        
        Args:
            event: Market event that triggered evaluation
            metadata: Optional metadata
            persist: Whether to save signals to database
            
        Returns:
            List of signal dictionaries from triggered strategies
        """
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

        # Generate signals from both strategies
        triggered_signals = []
        
        if STRATEGY_V1_AVAILABLE:
            signal_v1 = self.generate_signal(
                event.ticker,
                event.interval,
                'strategy_core_v1',
                event=event,
                metadata=sanitized_metadata,
            )
            if signal_v1 is not None:
                triggered_signals.append(signal_v1)
                if persist:
                    self.save_signal(signal_v1)
                    
                    # Track V1 persistence in pipeline
                    try:
                        signal_id = f"{signal_v1['ticker']}|{event.interval}|{signal_v1['timestamp']}|v1"
                        get_tracker().mark_persisted(signal_id=signal_id)
                    except Exception:
                        pass  # Never let tracker crash signal flow
                    
        if STRATEGY_V2_AVAILABLE:
            signal_v2 = self.generate_signal(
                event.ticker,
                event.interval,
                'strategy_core_v2',
                event=event,
                metadata=sanitized_metadata,
            )
            if signal_v2 is not None:
                triggered_signals.append(signal_v2)
                if persist:
                    self.save_signal(signal_v2)
                    
                    # Track V2 persistence in pipeline
                    try:
                        signal_id = f"{signal_v2['ticker']}|{event.interval}|{signal_v2['timestamp']}|v2"
                        get_tracker().mark_persisted(signal_id=signal_id)
                    except Exception:
                        pass  # Never let tracker crash signal flow

        if not triggered_signals:
            self._log_event_debug(
                {
                    'phase': 'event_no_signal',
                    'event': event_payload,
                    'reason': 'strategies_returned_neutral_or_none',
                    'trigger_metadata': sanitized_metadata,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                }
            )
            return []

        # Log summary for each triggered signal
        for signal_data in triggered_signals:
            signal_summary = {
                'ticker': signal_data['ticker'],
                'signal': signal_data['signal'],
                'signal_label': signal_data['signal_label'],
                'confidence': signal_data['confidence'],
                'source': signal_data.get('source', 'unknown'),
                'timestamp': signal_data['timestamp'],
            }

            self._log_event_debug(
                {
                    'phase': 'event_signal_generated',
                    'event': event_payload,
                    'trigger_metadata': sanitized_metadata,
                    'signal': signal_summary,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                }
            )

        return triggered_signals
    
    
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
