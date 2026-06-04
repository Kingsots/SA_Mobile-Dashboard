"""
TradeSignal dataclass representing a complete trade setup.

Combines:
- Direction from strategy (1=BUY, -1=SELL, 0=NEUTRAL)
- Entry price from current bar close
- Stop loss from rolling pivot structure
- Take profit from 2:1 risk-reward
- Status tracking and rejection reasons
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid


class TradeStatus(Enum):
    """Status of trade signal throughout its lifecycle."""
    CONSTRUCTED = "CONSTRUCTED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    SENT = "SENT"
    FILLED = "FILLED"
    CLOSED = "CLOSED"


@dataclass
class TradeSignal:
    """Complete trade signal with all execution prices and metadata."""
    
    # Core identification
    ticker: str
    interval: str
    strategy: str
    
    # Trade direction and prices
    direction: int  # 1=BUY, -1=SELL, 0=NEUTRAL
    entry_price: float
    stop_loss: float
    take_profit: float
    
    # Risk metrics
    risk_reward: float  # Ratio (e.g., 2.0 for 1:2)
    confidence: float = 1.0
    
    # Entry model type
    entry_type: str = 'breakout_confirmation'  # Indicates entry model used
    
    # Signal candle metadata
    signal_candle_time: Optional[int] = None  # Unix timestamp of signal candle
    expiry_candles: int = 6  # Number of candles until trade expires
    expiry_timestamp: Optional[int] = None  # Unix timestamp when signal expires
    
    # Status tracking
    status: str = field(default_factory=lambda: TradeStatus.CONSTRUCTED.value)
    rejection_reason: Optional[str] = None
    
    # Timestamps
    timestamp: datetime = field(default_factory=datetime.utcnow)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # Unique identifier
    trade_id: str = field(default_factory=lambda: 'PULSE-' + uuid.uuid4().hex[:4].upper())
    atr_value: float = 0.0
    
    def get_signal_label(self) -> str:
        """Return human-readable signal direction."""
        if self.direction == 1:
            return "BUY"
        elif self.direction == -1:
            return "SELL"
        else:
            return "NEUTRAL"
    
    def get_risk_amount(self) -> float:
        """Calculate absolute risk distance (entry to SL)."""
        return abs(self.entry_price - self.stop_loss)
    
    def get_reward_amount(self) -> float:
        """Calculate absolute reward distance (entry to TP)."""
        return abs(self.take_profit - self.entry_price)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'trade_id': self.trade_id,
            'ticker': self.ticker,
            'interval': self.interval,
            'strategy': self.strategy,
            'direction': self.direction,
            'signal_label': self.get_signal_label(),
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'risk_reward': self.risk_reward,
            'confidence': self.confidence,
            'entry_type': self.entry_type,
            'signal_candle_time': self.signal_candle_time,
            'expiry_candles': self.expiry_candles,
            'expiry_timestamp': self.expiry_timestamp,
            'status': self.status,
            'rejection_reason': self.rejection_reason,
            'risk_amount': self.get_risk_amount(),
            'reward_amount': self.get_reward_amount(),
            'timestamp': self.timestamp.isoformat(),
            'created_at': self.created_at.isoformat(),
        }
