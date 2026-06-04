"""
Signal Tracker
Track trading signals to differentiate NEW vs CONTINUATION alerts.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from pathlib import Path
from core.config import Config
from utils.logger import setup_logger

logger = setup_logger('SignalTracker')


class SignalTracker:
    """
    Track active trading signals to identify:
    - NEW signals (first-time alerts)
    - CONTINUATION signals (re-confirmations, volume spikes)
    
    Stores signal state in a JSON file for persistence.
    """
    
    def __init__(self, state_file: str = "signal_state.json"):
        """
        Initialize signal tracker
        
        Args:
            state_file: JSON file to store signal state
        """
        self.state_file = Path(state_file)
        self.active_signals = {}
        self.load_state()
        logger.info(f"Signal tracker initialized. Active signals: {len(self.active_signals)}")
    
    def load_state(self):
        """Load signal state from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    
                # Convert timestamp strings back to datetime
                for key, value in data.items():
                    if 'timestamp' in value:
                        value['timestamp'] = datetime.fromisoformat(value['timestamp'])
                    if 'last_alert' in value:
                        value['last_alert'] = datetime.fromisoformat(value['last_alert'])
                
                self.active_signals = data
                logger.info(f"Loaded {len(self.active_signals)} active signals from state file")
                
            except Exception as e:
                logger.error(f"Error loading signal state: {e}")
                self.active_signals = {}
        else:
            logger.info("No existing signal state file. Starting fresh.")
            self.active_signals = {}
    
    def save_state(self):
        """Save signal state to file"""
        try:
            # Convert datetime to ISO format strings
            data = {}
            for key, value in self.active_signals.items():
                data[key] = value.copy()
                if 'timestamp' in data[key]:
                    data[key]['timestamp'] = data[key]['timestamp'].isoformat()
                if 'last_alert' in data[key]:
                    data[key]['last_alert'] = data[key]['last_alert'].isoformat()
            
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving signal state: {e}")
    
    def get_signal_key(self, symbol: str, timeframe: str) -> str:
        """
        Generate unique key for symbol/timeframe combination
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
        
        Returns:
            Unique key string
        """
        return f"{symbol}_{timeframe}"
    
    def is_new_signal(self, symbol: str, timeframe: str, signal: str) -> Tuple[bool, str]:
        """
        Check if this is a NEW signal or CONTINUATION
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            signal: Signal type ('LONG' or 'SHORT')
        
        Returns:
            Tuple of (is_new: bool, alert_type: str)
        """
        key = self.get_signal_key(symbol, timeframe)
        
        # No previous signal - definitely NEW
        if key not in self.active_signals:
            logger.info(f"NEW signal: {symbol} {timeframe} {signal}")
            return True, 'NEW'
        
        prev_signal = self.active_signals[key]
        
        # Signal direction changed - NEW signal
        if prev_signal['signal'] != signal:
            logger.info(f"Direction changed: {symbol} {timeframe} {prev_signal['signal']} → {signal}")
            return True, 'NEW'
        
        # Same direction - check if enough time passed for continuation alert
        last_alert_time = prev_signal.get('last_alert', prev_signal['timestamp'])
        time_since_last = datetime.now() - last_alert_time
        
        # If enough time passed, send as CONTINUATION
        if time_since_last.total_seconds() >= Config.CONTINUATION_ALERT_INTERVAL:
            logger.info(f"CONTINUATION signal: {symbol} {timeframe} {signal} (last alert {time_since_last.total_seconds()/3600:.1f}h ago)")
            return False, 'CONTINUATION'
        
        # Too soon since last alert - skip
        logger.info(f"Skipping {symbol} {timeframe} {signal} - too soon since last alert ({time_since_last.total_seconds()/60:.0f}m)")
        return False, 'SKIP'
    
    def update_signal(self, symbol: str, timeframe: str, signal: str, 
                     confidence: float, price: float, send_alert: bool = True):
        """
        Update signal state
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            signal: Signal type
            confidence: Signal confidence
            price: Current price
            send_alert: Whether an alert was sent
        """
        key = self.get_signal_key(symbol, timeframe)
        now = datetime.now()
        
        if key in self.active_signals:
            # Update existing signal
            self.active_signals[key]['signal'] = signal
            self.active_signals[key]['confidence'] = confidence
            self.active_signals[key]['price'] = price
            self.active_signals[key]['count'] += 1
            
            if send_alert:
                self.active_signals[key]['last_alert'] = now
        else:
            # New signal
            self.active_signals[key] = {
                'symbol': symbol,
                'timeframe': timeframe,
                'signal': signal,
                'confidence': confidence,
                'price': price,
                'timestamp': now,
                'last_alert': now if send_alert else None,
                'count': 1
            }
        
        # Save state
        self.save_state()
        
        logger.info(f"Updated signal: {symbol} {timeframe} {signal} (count: {self.active_signals[key]['count']})")
    
    def clear_signal(self, symbol: str, timeframe: str):
        """
        Clear a signal (when it's no longer valid)
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
        """
        key = self.get_signal_key(symbol, timeframe)
        
        if key in self.active_signals:
            logger.info(f"Clearing signal: {symbol} {timeframe} {self.active_signals[key]['signal']}")
            del self.active_signals[key]
            self.save_state()
    
    def cleanup_old_signals(self, max_age_hours: int = 48):
        """
        Remove signals older than specified hours
        
        Args:
            max_age_hours: Maximum age in hours
        """
        now = datetime.now()
        to_remove = []
        
        for key, signal in self.active_signals.items():
            age = now - signal['timestamp']
            if age.total_seconds() > (max_age_hours * 3600):
                to_remove.append(key)
        
        for key in to_remove:
            logger.info(f"Removing old signal: {key}")
            del self.active_signals[key]
        
        if to_remove:
            self.save_state()
            logger.info(f"Cleaned up {len(to_remove)} old signals")
    
    def get_active_signals_summary(self) -> Dict:
        """
        Get summary of active signals
        
        Returns:
            Dictionary with summary statistics
        """
        summary = {
            'total': len(self.active_signals),
            'long': 0,
            'short': 0,
            'by_symbol': {},
            'by_timeframe': {}
        }
        
        for signal in self.active_signals.values():
            # Count by direction
            if signal['signal'] == 'LONG':
                summary['long'] += 1
            elif signal['signal'] == 'SHORT':
                summary['short'] += 1
            
            # Count by symbol
            symbol = signal['symbol']
            if symbol not in summary['by_symbol']:
                summary['by_symbol'][symbol] = 0
            summary['by_symbol'][symbol] += 1
            
            # Count by timeframe
            tf = signal['timeframe']
            if tf not in summary['by_timeframe']:
                summary['by_timeframe'][tf] = 0
            summary['by_timeframe'][tf] += 1
        
        return summary
    
    def get_signal_history(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """
        Get signal history for a specific symbol/timeframe
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
        
        Returns:
            Signal data or None
        """
        key = self.get_signal_key(symbol, timeframe)
        return self.active_signals.get(key)
    
    def should_send_alert(self, symbol: str, timeframe: str, signal: str) -> Tuple[bool, str]:
        """
        Determine if an alert should be sent
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            signal: Signal type
        
        Returns:
            Tuple of (should_send: bool, alert_type: str)
        """
        is_new, alert_type = self.is_new_signal(symbol, timeframe, signal)
        
        if alert_type == 'SKIP':
            return False, alert_type
        
        # Send NEW signals
        if is_new and Config.ALERT_NEW_SIGNALS:
            return True, 'NEW'
        
        # Send CONTINUATION signals if enabled
        if not is_new and alert_type == 'CONTINUATION' and Config.ALERT_CONTINUATION_SIGNALS:
            return True, 'CONTINUATION'
        
        return False, alert_type
