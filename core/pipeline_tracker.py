"""
Pipeline State Tracker - Observability Layer for Silent Analyst

Tracks signals through all pipeline stages without modifying trading logic.
Thread-safe in-memory tracking of:
- Event detection
- V1 directional signals
- V2 state machine stages (1A, 1B, 1C, 2, 3)
- Enrichment
- Persistence
- Broadcasting
"""

import threading
from typing import Dict, Any, Optional
from datetime import datetime, timezone


class PipelineTracker:
    """
    Thread-safe tracker for signal pipeline progression.
    
    Monitors:
    - Event → V1 → V2 Stages → Enrichment → Persistence → Broadcast
    
    Does NOT modify any trading logic or signal content.
    """
    
    def __init__(self):
        """Initialize tracker with locks and counters."""
        self._lock = threading.Lock()
        
        # Stage counters (last 24h)
        self.stage_counts = {
            "events": 0,           # Market events detected
            "v1": 0,               # V1 signals generated
            "stage1A": 0,          # RSI extreme visited
            "stage1B": 0,          # RSI break detected
            "stage1C": 0,          # Retest complete
            "stage2": 0,           # Entry window armed
            "stage3": 0,           # Entry fired
            "v2_enriched": 0,      # Real-time entry/SL/TP added
            "persisted": 0,        # Saved to database
            "broadcast": 0,        # Sent to Telegram
        }
        
        # Active signals in pipeline (signal_id → metadata)
        # signal_id format: "{ticker}|{interval}|{timestamp}|{direction}"
        self.active_pipeline: Dict[str, Dict[str, Any]] = {}
    
    def register_event(self, ticker: str, interval: str, event_type: str) -> str:
        """
        Register a market event entering the pipeline.
        
        Args:
            ticker: Trading symbol
            interval: Timeframe
            event_type: Event type (structure_break, volume_spike, etc.)
            
        Returns:
            Signal ID for tracking through pipeline
        """
        signal_id = f"{ticker}|{interval}|{datetime.now(timezone.utc).isoformat()}|{event_type}"
        
        with self._lock:
            self.stage_counts["events"] += 1
            self.active_pipeline[signal_id] = {
                "ticker": ticker,
                "interval": interval,
                "event_type": event_type,
                "current_stage": "event",
                "direction": None,
                "confidence": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        
        return signal_id
    
    def update_stage(self, signal_id: str, stage_name: str, 
                    direction: Optional[int] = None, 
                    confidence: Optional[float] = None) -> None:
        """
        Update signal's current stage in pipeline.
        
        Args:
            signal_id: Signal identifier
            stage_name: Stage name (v1, stage1A, stage1B, stage1C, stage2, stage3)
            direction: Signal direction (1=BUY, -1=SELL, 0=NEUTRAL)
            confidence: Confidence score (0.0-1.0)
        """
        with self._lock:
            # Increment stage counter if it exists
            if stage_name in self.stage_counts:
                self.stage_counts[stage_name] += 1
            
            # Update active signal metadata
            if signal_id in self.active_pipeline:
                self.active_pipeline[signal_id]["current_stage"] = stage_name
                if direction is not None:
                    self.active_pipeline[signal_id]["direction"] = direction
                if confidence is not None:
                    self.active_pipeline[signal_id]["confidence"] = confidence
    
    def mark_enriched(self, signal_id: str, entry_price: Optional[float] = None,
                     stop_loss: Optional[float] = None, 
                     take_profit: Optional[float] = None) -> None:
        """
        Mark signal as enriched by V2 execution engine.
        
        Args:
            signal_id: Signal identifier
            entry_price: Entry price calculated by V2
            stop_loss: Stop loss calculated by V2
            take_profit: Take profit calculated by V2
        """
        with self._lock:
            self.stage_counts["v2_enriched"] += 1
            
            if signal_id in self.active_pipeline:
                self.active_pipeline[signal_id]["enriched"] = True
                self.active_pipeline[signal_id]["entry_price"] = entry_price
                self.active_pipeline[signal_id]["stop_loss"] = stop_loss
                self.active_pipeline[signal_id]["take_profit"] = take_profit
                self.active_pipeline[signal_id]["enriched_at"] = datetime.now(timezone.utc).isoformat()
    
    def mark_persisted(self, signal_id: str, db_id: Optional[int] = None) -> None:
        """
        Mark signal as persisted to database.
        
        Args:
            signal_id: Signal identifier
            db_id: Database row ID for reference
        """
        with self._lock:
            self.stage_counts["persisted"] += 1
            
            if signal_id in self.active_pipeline:
                self.active_pipeline[signal_id]["persisted"] = True
                self.active_pipeline[signal_id]["db_id"] = db_id
                self.active_pipeline[signal_id]["persisted_at"] = datetime.now(timezone.utc).isoformat()
    
    def mark_broadcast(self, signal_id: str) -> None:
        """
        Mark signal as broadcast to Telegram.
        
        Args:
            signal_id: Signal identifier
        """
        with self._lock:
            self.stage_counts["broadcast"] += 1
            
            if signal_id in self.active_pipeline:
                self.active_pipeline[signal_id]["broadcast"] = True
                self.active_pipeline[signal_id]["broadcast_at"] = datetime.now(timezone.utc).isoformat()
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get current pipeline state summary.
        
        Returns:
            Dictionary with stage_counts and active_pipeline snapshot
        """
        with self._lock:
            return {
                "stage_counts": dict(self.stage_counts),
                "active_signals": len(self.active_pipeline),
                "active_pipeline": dict(self.active_pipeline),
            }
    
    def get_active_by_stage(self) -> Dict[str, list]:
        """
        Get active signals grouped by current stage.
        
        Returns:
            Dictionary mapping stage names to list of signals in that stage
        """
        grouped = {
            "event": [],
            "v1": [],
            "stage1A": [],
            "stage1B": [],
            "stage1C": [],
            "stage2": [],
            "stage3": [],
            "enriched": [],
            "persisted": [],
            "broadcast": [],
        }
        
        with self._lock:
            for signal_id, metadata in self.active_pipeline.items():
                stage = metadata.get("current_stage", "unknown")
                if stage in grouped:
                    grouped[stage].append({
                        "id": signal_id,
                        "ticker": metadata.get("ticker"),
                        "interval": metadata.get("interval"),
                        "direction": metadata.get("direction"),
                        "confidence": metadata.get("confidence"),
                    })
        
        return grouped
    
    def reset_counters(self) -> None:
        """Reset stage counters (call once per 24-hour period)."""
        with self._lock:
            for key in self.stage_counts:
                self.stage_counts[key] = 0
    
    def clear_inactive(self, max_age_seconds: int = 3600) -> None:
        """
        Remove signals older than max_age_seconds from active pipeline.
        
        Args:
            max_age_seconds: Age threshold in seconds (default 1 hour)
        """
        now = datetime.now(timezone.utc)
        cutoff = None
        
        with self._lock:
            expired_ids = []
            for signal_id, metadata in self.active_pipeline.items():
                try:
                    created = datetime.fromisoformat(metadata["created_at"])
                    age = (now - created).total_seconds()
                    if age > max_age_seconds:
                        expired_ids.append(signal_id)
                except:
                    pass
            
            for signal_id in expired_ids:
                del self.active_pipeline[signal_id]


# Global tracker instance
_tracker = PipelineTracker()


def get_tracker() -> PipelineTracker:
    """Get global pipeline tracker instance."""
    return _tracker
