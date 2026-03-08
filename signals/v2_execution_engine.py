"""
Real-time Execution Layer for V1 Signals

Responsibilities:
- Accept V1 directional signals
- Calculate entry price at broadcast time (real-time)
- Calculate stop loss from market structure
- Calculate take profit from risk/reward ratio
- Handle both BUY and SELL with correct math

NOT responsible for:
- Signal generation (V1 does this)
- State tracking (V2 strategy does this)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import pandas as pd
import numpy as np

from core.config import Config
from core.database import DatabaseManager

logger = logging.getLogger(__name__)


class V2ExecutionEngine:
    """
    Enriches V1 signals with real-time entry/SL/TP prices.
    
    Pipeline:
    1. Receive V1 signal {ticker, interval, signal, confidence}
    2. Load CURRENT OHLCV (not historical)
    3. Find market structure (swing highs/lows)
    4. Calculate entry at current price level
    5. Calculate SL and TP from structure
    6. Return enriched signal with all trade levels
    """
    
    def __init__(self):
        self.db = DatabaseManager()
    
    def execute_v1_signal(
        self,
        v1_signal: Dict[str, Any],
        live_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Enrich V1 signal with real-time execution prices.
        
        Args:
            v1_signal: V1 output {ticker, interval, signal, confidence, ...}
            live_price: Optional current bid/ask (if available from broker)
            
        Returns:
            Enriched signal with {entry_price, stop_loss, take_profit}
        """
        # Validate input
        required = ['ticker', 'interval', 'signal']
        if not all(k in v1_signal for k in required):
            raise ValueError(f"Missing required fields: {required}")
        
        ticker = v1_signal['ticker']
        interval = v1_signal['interval']
        signal = v1_signal['signal']
        
        # Guard: NEUTRAL signals don't get execution
        if signal == 0:
            logger.debug(f"{ticker}-{interval}: NEUTRAL signal, skipping execution")
            return v1_signal
        
        try:
            # Load CURRENT OHLCV (real-time, not event time)
            current_ohlcv = self._load_current_ohlcv(ticker, interval)
            if current_ohlcv is None or len(current_ohlcv) < 5:
                logger.warning(f"{ticker}-{interval}: Insufficient OHLCV data, using signal as-is")
                return v1_signal
            
            # Get current price
            current_price = live_price or float(current_ohlcv.iloc[-1]['close'])
            
            # Find market structure
            swing_high = self._find_swing_high(current_ohlcv, lookback=10)
            swing_low = self._find_swing_low(current_ohlcv, lookback=10)
            
            # Calculate execution prices
            if signal == 1:  # BUY
                entry = self._calculate_buy_entry(current_ohlcv, current_price)
                stop_loss = self._calculate_buy_stop_loss(swing_low)
                take_profit = self._calculate_buy_take_profit(entry, swing_low, swing_high)
            else:  # signal == -1, SELL
                entry = self._calculate_sell_entry(current_ohlcv, current_price)
                stop_loss = self._calculate_sell_stop_loss(swing_high)
                take_profit = self._calculate_sell_take_profit(entry, swing_low, swing_high)
            
            # Validate calculated prices
            if not self._validate_prices(signal, entry, stop_loss, take_profit):
                logger.warning(f"{ticker}-{interval}: Invalid price calculation, using signal as-is")
                return v1_signal
            
            # Enrich signal
            enriched = v1_signal.copy()
            enriched.update({
                'entry_price': round(float(entry), 5),
                'stop_loss': round(float(stop_loss), 5),
                'take_profit': round(float(take_profit), 5),
                'execution_source': 'v2_real_time',
                'calculated_at': datetime.now(timezone.utc).isoformat(),
                'current_price': round(float(current_price), 5),
            })
            
            logger.info(
                f"✅ {ticker}-{interval} [{v1_signal.get('signal_label', 'SIGNAL')}] "
                f"Entry: {enriched['entry_price']}, SL: {enriched['stop_loss']}, TP: {enriched['take_profit']}"
            )
            
            return enriched
            
        except Exception as e:
            logger.error(f"❌ Execution error {ticker}-{interval}: {e}")
            return v1_signal
    
    def _load_current_ohlcv(self, ticker: str, interval: str) -> Optional[pd.DataFrame]:
        """Load latest OHLCV data for ticker-interval."""
        try:
            data = self.db.get_ohlcv_data(ticker, interval, min_rows=20)
            return data if data is not None and len(data) >= 5 else None
        except Exception as e:
            logger.warning(f"Failed to load OHLCV {ticker}-{interval}: {e}")
            return None
    
    def _find_swing_high(self, ohlcv: pd.DataFrame, lookback: int = 10) -> float:
        """Find highest high in recent bars (resistance)."""
        if len(ohlcv) < lookback:
            lookback = len(ohlcv)
        return float(ohlcv['high'].tail(lookback).max())
    
    def _find_swing_low(self, ohlcv: pd.DataFrame, lookback: int = 10) -> float:
        """Find lowest low in recent bars (support)."""
        if len(ohlcv) < lookback:
            lookback = len(ohlcv)
        return float(ohlcv['low'].tail(lookback).min())
    
    def _calculate_buy_entry(self, ohlcv: pd.DataFrame, current: float) -> float:
        """Calculate entry price for BUY signal.
        
        Strategy: Enter at current price or recent pullback low if nearby.
        """
        try:
            recent_lows = ohlcv['low'].tail(5)
            threshold = current * 0.0001 if current > 100 else 0.001
            nearby_lows = [low for low in recent_lows if current - low < threshold]
            
            if nearby_lows:
                return min(nearby_lows)
            else:
                return current
        except Exception as e:
            logger.warning(f"Buy entry calculation error: {e}, using current")
            return current
    
    def _calculate_sell_entry(self, ohlcv: pd.DataFrame, current: float) -> float:
        """Calculate entry price for SELL signal.
        
        Strategy: Enter at current price or recent pullback high if nearby.
        """
        try:
            recent_highs = ohlcv['high'].tail(5)
            threshold = current * 0.0001 if current > 100 else 0.001
            nearby_highs = [high for high in recent_highs if high - current < threshold]
            
            if nearby_highs:
                return max(nearby_highs)
            else:
                return current
        except Exception as e:
            logger.warning(f"Sell entry calculation error: {e}, using current")
            return current
    
    def _calculate_buy_stop_loss(self, swing_low: float, buffer_pct: float = 0.005) -> float:
        """Stop loss for BUY: below swing support with buffer."""
        return swing_low * (1 - buffer_pct)
    
    def _calculate_sell_stop_loss(self, swing_high: float, buffer_pct: float = 0.005) -> float:
        """Stop loss for SELL: above swing resistance with buffer."""
        return swing_high * (1 + buffer_pct)
    
    def _calculate_buy_take_profit(
        self,
        entry: float,
        swing_low: float,
        swing_high: float,
        rr_ratio: float = 2.0,
    ) -> float:
        """Take profit for BUY: entry + (risk × R/R ratio)."""
        stop_loss = self._calculate_buy_stop_loss(swing_low)
        risk = entry - stop_loss
        return entry + (risk * rr_ratio)
    
    def _calculate_sell_take_profit(
        self,
        entry: float,
        swing_low: float,
        swing_high: float,
        rr_ratio: float = 2.0,
    ) -> float:
        """Take profit for SELL: entry - (risk × R/R ratio).
        
        NOTE: For shorts, TP is BELOW entry (correct direction).
        """
        stop_loss = self._calculate_sell_stop_loss(swing_high)
        risk = stop_loss - entry
        return entry - (risk * rr_ratio)
    
    def _validate_prices(
        self,
        signal: int,
        entry: float,
        stop_loss: float,
        take_profit: float,
    ) -> bool:
        """Validate calculated prices make logical sense."""
        try:
            if signal == 1:  # BUY
                if not (entry > stop_loss):
                    logger.warning(f"BUY: entry ({entry}) not > SL ({stop_loss})")
                    return False
                if not (take_profit > entry):
                    logger.warning(f"BUY: TP ({take_profit}) not > entry ({entry})")
                    return False
                rr_ratio = (take_profit - entry) / (entry - stop_loss) if entry != stop_loss else 0
                if rr_ratio < 1.5:
                    logger.warning(f"BUY: R/R ratio ({rr_ratio:.2f}:1) too low")
                    return False
            else:  # SELL
                if not (entry < stop_loss):
                    logger.warning(f"SELL: entry ({entry}) not < SL ({stop_loss})")
                    return False
                if not (take_profit < entry):
                    logger.warning(f"SELL: TP ({take_profit}) not < entry ({entry})")
                    return False
                rr_ratio = (entry - take_profit) / (stop_loss - entry) if stop_loss != entry else 0
                if rr_ratio < 1.5:
                    logger.warning(f"SELL: R/R ratio ({rr_ratio:.2f}:1) too low")
                    return False
            
            return True
        except Exception as e:
            logger.warning(f"Price validation error: {e}")
            return False
