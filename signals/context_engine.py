"""
Context Engine - Compression/Expansion and Liquidity Detection
Provides market structure intelligence for Silent Analyst trading system

Read-only observation layer (Phase 1): Computes context and logs to database
Does NOT filter signals or modify strategy logic (CONTEXT_ENGINE_FILTER_ENABLED=False)

Phase 2 (future): Can influence EventMonitor and Strategies after 2-week observation
"""

import logging
from typing import Dict, Optional, List
import pandas as pd
import numpy as np

from core.config import Config

logger = logging.getLogger(__name__)


class ContextEngine:
    """
    Market context intelligence engine
    
    Computes 7 context fields from feature-enriched DataFrame:
    - compression_score: ATR-based volatility compression
    - expansion_pressure: Probability of volatility expansion [0.0-1.0]
    - rsi_stage: Structural RSI classification (1A/1B/1C/NEUTRAL)
    - nearest_liquidity: Closest liquidity pool price
    - liquidity_type: Pool type (equal_high/equal_low/session_high/session_low/none)
    - distance_to_liquidity: Raw absolute price delta to nearest pool (not pip-normalised)
    - distance_to_liquidity_pct: Normalised distance as % of current price. None when no pool found.
    - liquidity_sweep: Sweep through pool detected (high confidence only)
    """
    
    def compute_context(
        self,
        df: pd.DataFrame,
        ticker: str,
        interval: str
    ) -> Dict:
        """
        Orchestrate all context computations
        
        Args:
            df: Feature-enriched DataFrame with OHLCV + all indicators
            ticker: Symbol (for debugging/logging)
            interval: Timeframe (for debugging/logging)
        
        Returns:
            Dict with 7 context fields, or safe defaults on exception
        """
        try:
            # Validate input
            if df is None or df.empty or len(df) < 20:
                return self._safe_default()
            
            # Sequence: compression → pressure → RSI stage → pools → nearest → sweep
            compression_score = self._compute_compression(df)
            expansion_pressure = self._compute_expansion_pressure(df, compression_score)
            rsi_stage = self._detect_rsi_stage(df, compression_score)
            pools = self._detect_liquidity_pools(df, ticker)
            nearest = self._find_nearest_pool(df, pools)
            sweep = self._detect_liquidity_sweep(df, pools)
            
            current_price = float(df.iloc[-1]['close'])
            wick = self._compute_wick_intelligence(
                df=df,
                current_price=current_price,
                distance_to_liquidity=nearest["distance_to_liquidity"],
                liquidity_sweep=sweep,
            )

            return {
                "compression_score":         compression_score,
                "expansion_pressure":        expansion_pressure,
                "rsi_stage":                 rsi_stage,
                "nearest_liquidity":         nearest["nearest_liquidity"],
                "liquidity_type":            nearest["liquidity_type"],
                "distance_to_liquidity":     nearest["distance_to_liquidity"],
                "distance_to_liquidity_pct": nearest["distance_to_liquidity_pct"],
                "liquidity_sweep":           sweep,
                "rejection_strength":        wick["rejection_strength"],
                "breakout_quality":          wick["breakout_quality"],
                "body_commitment":           wick["body_commitment"],
                "sweep_probability":         wick["sweep_probability"],
            }
            
        except Exception as e:
            logger.error(f"[CONTEXT] Computation failed: {e}", exc_info=False)
            return self._safe_default()
    
    @staticmethod
    def _safe_default() -> Dict:
        """Safe default context when computation fails or data insufficient"""
        return {
            "compression_score": 1.0,
            "expansion_pressure": 0.0,
            "rsi_stage": "NEUTRAL",
            "nearest_liquidity": 0.0,
            "liquidity_type": "none",
            "distance_to_liquidity": None,
            "distance_to_liquidity_pct": None,
            "liquidity_sweep": False
        }
    
    # ========================================================================
    # FUNCTION 1: Compression Score (ATR-based volatility ratio)
    # ========================================================================
    
    @staticmethod
    def _compute_compression(df: pd.DataFrame) -> float:
        """
        Compute ATR-based compression score
        
        compression_score = current_atr / atr_sma_20
        
        < 0.6  → compression (tight, energy building)
        0.6–0.8 → contracting
        0.8–1.2 → normal
        > 1.2  → expansion
        
        Args:
            df: DataFrame with 'atr_14' and 'atr_sma_20' columns
        
        Returns:
            float (ratio, unbounded)
        """
        try:
            if 'atr_14' not in df.columns or 'atr_sma_20' not in df.columns:
                return 1.0
            
            current_atr = df['atr_14'].iloc[-1]
            atr_sma_20 = df['atr_sma_20'].iloc[-1]
            
            if pd.isna(current_atr) or pd.isna(atr_sma_20):
                return 1.0
            
            if atr_sma_20 == 0 or atr_sma_20 < 1e-10:
                return 1.0
            
            compression_score = current_atr / atr_sma_20
            return float(compression_score)
            
        except Exception:
            return 1.0
    
    # ========================================================================
    # FUNCTION 2: Expansion Pressure (Normalized [0.0-1.0])
    # ========================================================================
    
    @staticmethod
    def _compute_expansion_pressure(df: pd.DataFrame, compression_score: float) -> float:
        """
        Estimate probability of volatility expansion
        
        CRITICAL: All three sub-components MUST be independently normalized 
        to [0.0, 1.0] before averaging to ensure result is always [0.0, 1.0]
        
        Sub-components:
        1. compression_strength: How tight the market is (0.0-1.0)
        2. volume_accumulation: Volume relative to average (0.0-1.0)
        3. range_contraction: Candle range vs ATR (0.0-1.0)
        
        Args:
            df: Feature-enriched DataFrame
            compression_score: Already-computed compression ratio
        
        Returns:
            float between 0.0 and 1.0
        """
        try:
            # ===== SUB-COMPONENT 1: Compression Strength =====
            # Inverted: more compressed = higher score
            raw_compression = 1.0 - compression_score
            compression_strength = max(0.0, min(1.0, raw_compression))
            
            # ===== SUB-COMPONENT 2: Volume Accumulation =====
            # Normalize unbounded volume_ratio [0.5-2.5] to [0.0-1.0]
            try:
                volume_ratio = df['volume_ratio'].iloc[-1]
                if pd.isna(volume_ratio) or volume_ratio <= 0:
                    volume_accumulation = 0.0
                else:
                    # Map 0.5→0.0, 1.5→0.5, 2.5→1.0
                    FLOOR = 0.5
                    CEILING = 2.5
                    raw_ratio = (volume_ratio - FLOOR) / (CEILING - FLOOR)
                    volume_accumulation = max(0.0, min(1.0, raw_ratio))
            except Exception:
                volume_accumulation = 0.0
            
            # ===== SUB-COMPONENT 3: Range Contraction =====
            # Measures how much last candle range contracted vs ATR
            try:
                if len(df) < 2:
                    range_contraction = 0.0
                else:
                    last_candle_range = df['high'].iloc[-1] - df['low'].iloc[-1]
                    current_atr = df['atr_14'].iloc[-1]
                    
                    if current_atr == 0 or pd.isna(current_atr):
                        range_contraction = 0.0
                    else:
                        raw_ratio = last_candle_range / current_atr
                        # Inverted: smaller range = higher contraction score
                        range_contraction = 1.0 - max(0.0, min(1.0, raw_ratio))
            except Exception:
                range_contraction = 0.0
            
            # ===== FINAL FORMULA =====
            # All three are now guaranteed [0.0, 1.0]
            expansion_pressure = (
                compression_strength
                + volume_accumulation
                + range_contraction
            ) / 3.0
            
            # Final clamp (defensive)
            return max(0.0, min(1.0, expansion_pressure))
            
        except Exception:
            return 0.0
    
    # ========================================================================
    # FUNCTION 3: RSI Stage Detection
    # ========================================================================
    
    @staticmethod
    def _detect_rsi_stage(df: pd.DataFrame, compression_score: float) -> str:
        """
        Detect structural RSI stage
        
        Stage 1A: RSI <40 with compression (accumulation)
        Stage 1B: RSI 40-60 with compression (pressure building)
        Stage 1C: RSI >60 and expanding (breakout)
        NEUTRAL: No clear stage
        
        Uses existing df['rsi_14'] — no recomputation
        
        Args:
            df: DataFrame with 'rsi_14' column
            compression_score: Compression ratio
        
        Returns:
            str: One of "1A", "1B", "1C", "NEUTRAL"
        """
        try:
            if 'rsi_14' not in df.columns or len(df) < 20:
                return "NEUTRAL"
            
            rsi = df['rsi_14'].iloc[-1]
            
            if pd.isna(rsi):
                return "NEUTRAL"
            
            is_compressing = compression_score < 0.8
            
            if rsi < 40 and is_compressing:
                return "1A"
            elif 40 <= rsi <= 60 and is_compressing:
                return "1B"
            elif rsi > 60 and not is_compressing:
                return "1C"
            else:
                return "NEUTRAL"
                
        except Exception:
            return "NEUTRAL"
    
    # ========================================================================
    # FUNCTION 4: Liquidity Pool Detection
    # ========================================================================
    
    @staticmethod
    def _detect_liquidity_pools(df: pd.DataFrame, ticker: str) -> List[Dict]:
        """
        Identify liquidity clusters using swing highs/lows
        
        REUSES range_detection.py logic for swing identification.
        Tolerance is ATR-relative (not hardcoded).
        
        Pool types:
        - "equal_high": Clustered swing highs
        - "equal_low": Clustered swing lows
        - "session_high": Max of last 20 bars
        - "session_low": Min of last 20 bars
        
        Args:
            df: Feature-enriched DataFrame (need 'atr_14')
            ticker: Symbol (for debugging)
        
        Returns:
            List of pools [{"price": float, "type": str}, ...]
        """
        try:
            if df is None or df.empty or len(df) < 30:
                return []
            
            pools = []
            
            # ===== Step 1: Get recent swing highs and lows =====
            lookback_window = min(50, len(df))
            recent_df = df.tail(lookback_window)
            
            # Detect swing highs (local maxima in rolling 5-bar window)
            swing_window = 5
            rolling_highs = recent_df['high'].rolling(window=swing_window, center=True).max()
            rolling_lows = recent_df['low'].rolling(window=swing_window, center=True).min()
            
            # Extract unique swing levels
            swing_high_list = rolling_highs[rolling_highs == recent_df['high']].unique()
            swing_low_list = rolling_lows[rolling_lows == recent_df['low']].unique()
            
            # ===== Step 2: Calculate ATR-relative tolerance =====
            atr_value = df['atr_14'].iloc[-1]
            if pd.isna(atr_value) or atr_value == 0:
                tolerance = 0.0001  # Fallback: 0.01%
            else:
                tolerance = atr_value * 0.3  # 30% of current ATR
            
            # ===== Step 3: Cluster equal highs =====
            for i, h1 in enumerate(swing_high_list):
                if pd.isna(h1):
                    continue
                for h2 in swing_high_list[i+1:]:
                    if pd.isna(h2):
                        continue
                    if abs(h1 - h2) < tolerance:
                        pool_price = (h1 + h2) / 2
                        pools.append({"price": pool_price, "type": "equal_high"})
            
            # ===== Step 4: Cluster equal lows =====
            for i, l1 in enumerate(swing_low_list):
                if pd.isna(l1):
                    continue
                for l2 in swing_low_list[i+1:]:
                    if pd.isna(l2):
                        continue
                    if abs(l1 - l2) < tolerance:
                        pool_price = (l1 + l2) / 2
                        pools.append({"price": pool_price, "type": "equal_low"})
            
            # ===== Step 5: Add session extremes =====
            session_high = recent_df['high'].max()
            session_low = recent_df['low'].min()
            
            if not pd.isna(session_high):
                pools.append({"price": session_high, "type": "session_high"})
            if not pd.isna(session_low):
                pools.append({"price": session_low, "type": "session_low"})
            
            # ===== Step 6: Deduplicate =====
            seen = set()
            dedup_pools = []
            for pool in sorted(pools, key=lambda x: x["price"]):
                key = (round(pool["price"], 6), pool["type"])
                if key not in seen:
                    seen.add(key)
                    dedup_pools.append(pool)
            
            return dedup_pools
            
        except Exception as e:
            logger.debug(f"[CONTEXT] Liquidity pool detection failed for {ticker}: {e}")
            return []
    
    # ========================================================================
    # FUNCTION 5: Find Nearest Pool
    # ========================================================================
    
    @staticmethod
    def _find_nearest_pool(df: pd.DataFrame, pools: List[Dict]) -> Dict:
        """
        Find closest liquidity pool to current price
        
        Args:
            df: DataFrame with 'close' column
            pools: List from _detect_liquidity_pools()
        
        Returns:
            {
                "nearest_liquidity": float (price or 0.0),
                "liquidity_type": str (type or "none"),
                "distance_to_liquidity": Raw absolute price delta to nearest pool
                    (not pip-normalised). Normalised percentage stored separately
                    in distance_to_liquidity_pct. None when no pool found.
            }
        """
        try:
            if not pools or len(df) == 0:
                return {
                    "nearest_liquidity": 0.0,
                    "liquidity_type": "none",
                    "distance_to_liquidity": None,
                    "distance_to_liquidity_pct": None,
                }
            
            current_price = df['close'].iloc[-1]
            
            if pd.isna(current_price):
                return {
                    "nearest_liquidity": 0.0,
                    "liquidity_type": "none",
                    "distance_to_liquidity": None,
                    "distance_to_liquidity_pct": None,
                }
            
            # Find closest pool
            closest_pool = None
            min_distance = float('inf')
            
            for pool in pools:
                distance = abs(current_price - pool["price"])
                if distance < min_distance:
                    min_distance = distance
                    closest_pool = pool
            
            if closest_pool is None:
                return {
                    "nearest_liquidity": 0.0,
                    "liquidity_type": "none",
                    "distance_to_liquidity": None,
                    "distance_to_liquidity_pct": None,
                }
            
            dist_pct = round(min_distance / current_price * 100, 6) \
                       if current_price and current_price > 0 else None
            return {
                "nearest_liquidity":         closest_pool["price"],
                "liquidity_type":            closest_pool["type"],
                "distance_to_liquidity":     min_distance,
                "distance_to_liquidity_pct": dist_pct,
            }
            
        except Exception:
            return {
                "nearest_liquidity": 0.0,
                "liquidity_type": "none",
                "distance_to_liquidity": None,
                "distance_to_liquidity_pct": None,
            }
    
    # ========================================================================
    # FUNCTION 6: Liquidity Sweep Detection
    # ========================================================================
    
    @staticmethod
    def _detect_liquidity_sweep(df: pd.DataFrame, pools: List[Dict]) -> bool:
        """
        Detect high-confidence liquidity sweeps
        
        Requires ALL THREE conditions:
        1. Price broke through liquidity pool
        2. Confirmation candle closed back inside (reversal)
        3. Volume above average AND wick-to-body ratio >= 1.5
        
        Examines last 3 bars for sweep pattern.
        
        Args:
            df: Feature-enriched DataFrame
            pools: List from _detect_liquidity_pools()
        
        Returns:
            bool: True only on high-confidence sweep, False otherwise
        """
        try:
            if df is None or len(df) < 4 or not pools:
                return False
            
            # Get last 3 bars
            bar_minus_2 = df.iloc[-3]  # Sweep candle (breaks level)
            bar_minus_1 = df.iloc[-2]  # Reversal candle (closes back inside)
            bar_minus_0 = df.iloc[-1]  # Current candle
            
            # Get threshold for volume
            if 'volume_sma_20' not in df.columns:
                return False
            
            avg_volume = df['volume_sma_20'].iloc[-2]
            
            # Check each pool for sweep pattern
            for pool in pools:
                pool_level = pool["price"]
                pool_type = pool["type"]
                
                # ===== LONG SWEEP: Equal High / Session High =====
                if pool_type in ["equal_high", "session_high"]:
                    # Conditions:
                    # 1. High broke above
                    # 2. Close reversed back below
                    # 3. Volume confirmation
                    # 4. Wick-to-body ratio >= 1.5
                    
                    broke_high = bar_minus_2['high'] > pool_level
                    reversed_below = bar_minus_1['close'] < pool_level
                    volume_confirmed = bar_minus_1['volume'] > avg_volume
                    
                    if broke_high and reversed_below and volume_confirmed:
                        # Calculate wick-to-body ratio
                        candle_body = abs(bar_minus_2['close'] - bar_minus_2['open'])
                        candle_wick = bar_minus_2['high'] - pool_level
                        
                        if candle_body > 1e-10:
                            wick_to_body = candle_wick / candle_body
                            if wick_to_body >= 1.5:
                                return True
                
                # ===== SHORT SWEEP: Equal Low / Session Low =====
                elif pool_type in ["equal_low", "session_low"]:
                    # Conditions:
                    # 1. Low broke below
                    # 2. Close reversed back above
                    # 3. Volume confirmation
                    # 4. Wick-to-body ratio >= 1.5
                    
                    broke_low = bar_minus_2['low'] < pool_level
                    reversed_above = bar_minus_1['close'] > pool_level
                    volume_confirmed = bar_minus_1['volume'] > avg_volume
                    
                    if broke_low and reversed_above and volume_confirmed:
                        # Calculate wick-to-body ratio
                        candle_body = abs(bar_minus_2['close'] - bar_minus_2['open'])
                        candle_wick = pool_level - bar_minus_2['low']
                        
                        if candle_body > 1e-10:
                            wick_to_body = candle_wick / candle_body
                            if wick_to_body >= 1.5:
                                return True
            
            return False
            
        except Exception:
            return False

    # ========================================================================
    # FUNCTION 7: Wick Intelligence
    # ========================================================================

    def _compute_wick_intelligence(self, df, current_price,
                                   distance_to_liquidity, liquidity_sweep):
        """
        Computes 4 wick-based metrics on the most recent completed bar.
        Called last in compute_context() -- depends on upstream outputs.

        Returns dict with keys:
          distance_to_liquidity_pct  -- normalised distance as % of price
          rejection_strength         -- directional wick / total_range [0.0-1.0]
          breakout_quality           -- body / total_range [0.0-1.0]
          body_commitment            -- body / atr_14 [0.0-inf, typically 0.1-1.5]
          sweep_probability          -- graduated likelihood [0.0-1.0]
        """
        _null = {
            "distance_to_liquidity_pct": None,
            "rejection_strength":        None,
            "breakout_quality":          None,
            "body_commitment":           None,
            "sweep_probability":         None,
        }

        try:
            last = df.iloc[-1]
            o = float(last['open'])
            h = float(last['high'])
            l = float(last['low'])
            c = float(last['close'])
            atr_14 = float(last['atr_14'])

            total_range = h - l

            # Guard -- doji / zero-range bar / bad ATR
            if total_range <= 0 or atr_14 <= 0 or not current_price \
                    or current_price <= 0:
                return _null

            # 1. distance_to_liquidity_pct
            if distance_to_liquidity is None:
                dist_pct = None
            else:
                dist_pct = round(
                    float(distance_to_liquidity) / current_price * 100, 6
                )

            # 2. rejection_strength -- directional
            body_size  = abs(c - o)
            upper_wick = h - max(o, c)
            lower_wick = min(o, c) - l
            is_bearish = c < o

            rejection = upper_wick if is_bearish else lower_wick
            rejection_strength = round(rejection / total_range, 4)

            # 3. breakout_quality
            breakout_quality = round(body_size / total_range, 4)

            # 4. body_commitment
            body_commitment = round(body_size / atr_14, 4)

            # 5. sweep_probability
            score = 0.0

            wick_to_body = rejection / body_size if body_size > 0 else 3.0
            if   wick_to_body >= 2.0: score += 0.40
            elif wick_to_body >= 1.5: score += 0.25
            elif wick_to_body >= 1.0: score += 0.10

            if dist_pct is not None:
                if   dist_pct < 0.30: score += 0.30
                elif dist_pct < 0.80: score += 0.15

            if liquidity_sweep:
                score += 0.30

            sweep_probability = round(min(1.0, score), 4)

            return {
                "distance_to_liquidity_pct": dist_pct,
                "rejection_strength":        rejection_strength,
                "breakout_quality":          breakout_quality,
                "body_commitment":           body_commitment,
                "sweep_probability":         sweep_probability,
            }

        except Exception:
            return _null
