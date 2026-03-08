"""
Entry Rules Engine
Implements exact Pine Script entry logic with strict engulfing patterns.
"""

import pandas as pd
from typing import Tuple, Dict
from core.indicators import TechnicalIndicators
from core.config import Config
from .volume_filter import VolumeFilter


class EntryRules:
    """
    Entry rules matching your Pine Script OptiCore strategy.
    
    LONG Entry Requirements (ALL must be TRUE):
    1. Strict bullish engulfing pattern (if STRICT_ENGULFING = True)
    2. Close > EMA 21
    3. RSI > 50
    4. Volume > 1.2x average
    5. Daily close > Daily EMA 100
    
    SHORT Entry Requirements (ALL must be TRUE):
    1. Strict bearish engulfing pattern (if STRICT_ENGULFING = True)
    2. Close < EMA 21
    3. RSI < 50
    4. Volume > 1.2x average
    5. Daily close < Daily EMA 100
    """
    
    def __init__(self, strict_engulfing: bool = None):
        """
        Initialize entry rules
        
        Args:
            strict_engulfing: Use strict engulfing patterns (default: from config)
        """
        self.strict_engulfing = strict_engulfing if strict_engulfing is not None else Config.STRICT_ENGULFING
    
    def check_long_entry(self, current_df: pd.DataFrame, daily_df: pd.DataFrame = None) -> Tuple[bool, Dict]:
        """
        Check if LONG entry conditions are met
        
        Pine Script equivalent:
        longCondition = bullEngulfValid and (close > emaFilter) and 
                       (rsiVal > 50) and (volume > avgVol * volMult)
        longCondition := useHTF ? (longCondition and dailyClose > dailyEma) : longCondition
        
        Args:
            current_df: Current timeframe DataFrame (30m or 1h)
            daily_df: Daily timeframe DataFrame (for HTF filter)
        
        Returns:
            Tuple of (entry_valid: bool, analysis: dict)
        """
        if current_df is None or current_df.empty or len(current_df) < 30:
            return False, {'error': 'Insufficient data'}
        
        analysis = {}
        
        try:
            # 1. Check engulfing pattern
            if self.strict_engulfing:
                engulfing_valid = TechnicalIndicators.is_strict_bullish_engulfing(current_df)
                analysis['pattern'] = 'strict_bullish_engulfing' if engulfing_valid else 'none'
            else:
                engulfing_valid = TechnicalIndicators.is_bullish_candle(current_df)
                analysis['pattern'] = 'bullish_candle' if engulfing_valid else 'none'
            
            # 2. Check EMA condition (close > EMA 21)
            current_close = float(current_df['close'].iloc[-1])
            ema_21 = TechnicalIndicators.calculate_ema(current_df['close'], Config.EMA_LTF)
            ema_valid = current_close > ema_21
            
            analysis['current_price'] = current_close
            analysis['ema_21'] = ema_21
            analysis['above_ema'] = ema_valid
            
            # 3. Check RSI condition (RSI > 50)
            rsi = TechnicalIndicators.calculate_rsi(current_df['close'], Config.RSI_PERIOD)
            rsi_valid = rsi > Config.RSI_LONG_THRESHOLD
            
            analysis['rsi'] = rsi
            analysis['rsi_valid'] = rsi_valid
            
            # 4. Check volume spike (volume > 1.2x average)
            volume_spike, volume_data = VolumeFilter.check_volume_spike(current_df)
            analysis['volume'] = volume_data
            analysis['volume_valid'] = volume_spike
            
            # 5. Check Daily HTF filter (if daily data provided)
            htf_valid = True  # Default to True if no daily data
            if daily_df is not None and not daily_df.empty:
                daily_close = float(daily_df['close'].iloc[-1])
                daily_ema_100 = TechnicalIndicators.calculate_ema(daily_df['close'], Config.EMA_HTF)
                htf_valid = daily_close > daily_ema_100
                
                analysis['daily_price'] = daily_close
                analysis['daily_ema_100'] = daily_ema_100
                analysis['daily_bullish'] = htf_valid
            else:
                analysis['daily_bullish'] = None  # No daily data
            
            # ALL conditions must be TRUE
            entry_valid = (
                engulfing_valid and
                ema_valid and
                rsi_valid and
                volume_spike and
                htf_valid
            )
            
            analysis['entry_valid'] = entry_valid
            analysis['signal_type'] = 'LONG'
            analysis['conditions_met'] = {
                'engulfing': engulfing_valid,
                'ema': ema_valid,
                'rsi': rsi_valid,
                'volume': volume_spike,
                'daily': htf_valid
            }
            
            # Calculate confidence
            conditions_count = sum(analysis['conditions_met'].values())
            analysis['confidence'] = (conditions_count / 5) * 100  # 5 total conditions
            
            return entry_valid, analysis
            
        except Exception as e:
            print(f"Long entry check error: {e}")
            return False, {'error': str(e)}
    
    def check_short_entry(self, current_df: pd.DataFrame, daily_df: pd.DataFrame = None) -> Tuple[bool, Dict]:
        """
        Check if SHORT entry conditions are met
        
        Pine Script equivalent:
        shortCondition = bearEngulfValid and (close < emaFilter) and 
                        (rsiVal < 50) and (volume > avgVol * volMult)
        shortCondition := useHTF ? (shortCondition and dailyClose < dailyEma) : shortCondition
        
        Args:
            current_df: Current timeframe DataFrame (30m or 1h)
            daily_df: Daily timeframe DataFrame (for HTF filter)
        
        Returns:
            Tuple of (entry_valid: bool, analysis: dict)
        """
        if current_df is None or current_df.empty or len(current_df) < 30:
            return False, {'error': 'Insufficient data'}
        
        analysis = {}
        
        try:
            # 1. Check engulfing pattern
            if self.strict_engulfing:
                engulfing_valid = TechnicalIndicators.is_strict_bearish_engulfing(current_df)
                analysis['pattern'] = 'strict_bearish_engulfing' if engulfing_valid else 'none'
            else:
                engulfing_valid = TechnicalIndicators.is_bearish_candle(current_df)
                analysis['pattern'] = 'bearish_candle' if engulfing_valid else 'none'
            
            # 2. Check EMA condition (close < EMA 21)
            current_close = float(current_df['close'].iloc[-1])
            ema_21 = TechnicalIndicators.calculate_ema(current_df['close'], Config.EMA_LTF)
            ema_valid = current_close < ema_21
            
            analysis['current_price'] = current_close
            analysis['ema_21'] = ema_21
            analysis['below_ema'] = ema_valid
            
            # 3. Check RSI condition (RSI < 50)
            rsi = TechnicalIndicators.calculate_rsi(current_df['close'], Config.RSI_PERIOD)
            rsi_valid = rsi < Config.RSI_SHORT_THRESHOLD
            
            analysis['rsi'] = rsi
            analysis['rsi_valid'] = rsi_valid
            
            # 4. Check volume spike (volume > 1.2x average)
            volume_spike, volume_data = VolumeFilter.check_volume_spike(current_df)
            analysis['volume'] = volume_data
            analysis['volume_valid'] = volume_spike
            
            # 5. Check Daily HTF filter (if daily data provided)
            htf_valid = True  # Default to True if no daily data
            if daily_df is not None and not daily_df.empty:
                daily_close = float(daily_df['close'].iloc[-1])
                daily_ema_100 = TechnicalIndicators.calculate_ema(daily_df['close'], Config.EMA_HTF)
                htf_valid = daily_close < daily_ema_100
                
                analysis['daily_price'] = daily_close
                analysis['daily_ema_100'] = daily_ema_100
                analysis['daily_bearish'] = htf_valid
            else:
                analysis['daily_bearish'] = None  # No daily data
            
            # ALL conditions must be TRUE
            entry_valid = (
                engulfing_valid and
                ema_valid and
                rsi_valid and
                volume_spike and
                htf_valid
            )
            
            analysis['entry_valid'] = entry_valid
            analysis['signal_type'] = 'SHORT'
            analysis['conditions_met'] = {
                'engulfing': engulfing_valid,
                'ema': ema_valid,
                'rsi': rsi_valid,
                'volume': volume_spike,
                'daily': htf_valid
            }
            
            # Calculate confidence
            conditions_count = sum(analysis['conditions_met'].values())
            analysis['confidence'] = (conditions_count / 5) * 100  # 5 total conditions
            
            return entry_valid, analysis
            
        except Exception as e:
            print(f"Short entry check error: {e}")
            return False, {'error': str(e)}
    
    def check_entry(self, current_df: pd.DataFrame, daily_df: pd.DataFrame = None) -> Tuple[str, Dict]:
        """
        Check both LONG and SHORT entry conditions
        
        Args:
            current_df: Current timeframe DataFrame
            daily_df: Daily timeframe DataFrame
        
        Returns:
            Tuple of (signal: str, analysis: dict)
            signal: 'LONG', 'SHORT', or 'HOLD'
        """
        # Check LONG
        long_valid, long_analysis = self.check_long_entry(current_df, daily_df)
        
        # Check SHORT
        short_valid, short_analysis = self.check_short_entry(current_df, daily_df)
        
        # Determine signal
        if long_valid and not short_valid:
            return 'LONG', long_analysis
        elif short_valid and not long_valid:
            return 'SHORT', short_analysis
        elif long_valid and short_valid:
            # Conflict - should not happen with proper logic, but just in case
            return 'HOLD', {'error': 'Conflicting signals'}
        else:
            return 'HOLD', {'message': 'No valid entry conditions'}
    
    def format_entry_summary(self, signal: str, analysis: Dict) -> str:
        """
        Format entry analysis for display
        
        Args:
            signal: Signal type ('LONG', 'SHORT', 'HOLD')
            analysis: Analysis dictionary
        
        Returns:
            Formatted string
        """
        if 'error' in analysis:
            return f"❌ Error: {analysis['error']}"
        
        if signal == 'HOLD':
            return "⚪ HOLD - No valid entry conditions"
        
        lines = []
        lines.append(f"{'🟢' if signal == 'LONG' else '🔴'} {signal} SIGNAL")
        lines.append("=" * 40)
        
        # Conditions checklist
        conditions = analysis.get('conditions_met', {})
        lines.append("Entry Conditions:")
        for condition, met in conditions.items():
            icon = "✅" if met else "❌"
            lines.append(f"  {icon} {condition.upper()}")
        
        # Price and indicators
        lines.append("")
        lines.append(f"Price: {analysis.get('current_price', 0):.2f}")
        lines.append(f"EMA(21): {analysis.get('ema_21', 0):.2f}")
        lines.append(f"RSI(14): {analysis.get('rsi', 0):.1f}")
        
        if 'volume' in analysis:
            vol = analysis['volume']
            lines.append(f"Volume: {vol['current_volume']:,.0f} ({vol['ratio']:.2f}x avg)")
        
        if analysis.get('daily_price'):
            lines.append(f"Daily: {analysis['daily_price']:.2f} (EMA100: {analysis['daily_ema_100']:.2f})")
        
        lines.append(f"Confidence: {analysis.get('confidence', 0):.0f}%")
        
        return "\n".join(lines)
