"""
Multi-Timeframe Analyzer
Analyzes trend alignment across Daily → 4H → 2H → 1H → 30m timeframes.
"""

import pandas as pd
from typing import Dict, List, Tuple
from .indicators import TechnicalIndicators
from .config import Config


class MultiTimeframeAnalyzer:
    """
    Analyzes multiple timeframes to ensure trend alignment.
    
    Your requirement: "Daily → 4H → 2H → 1H → 30m must ALL align"
    
    For a LONG signal:
    - All timeframes must be bullish (price > EMA)
    - Daily must be above Daily EMA 100
    - All lower timeframes must confirm uptrend
    
    For a SHORT signal:
    - All timeframes must be bearish (price < EMA)
    - Daily must be below Daily EMA 100
    - All lower timeframes must confirm downtrend
    """
    
    def __init__(self):
        self.config = Config()
    
    def analyze_timeframe(self, df: pd.DataFrame, timeframe: str, ema_period: int = None) -> Dict:
        """
        Analyze a single timeframe for trend direction
        
        Args:
            df: DataFrame with OHLCV data
            timeframe: Timeframe identifier ('1d', '4h', '2h', '1h', '30m')
            ema_period: EMA period to use (default: auto-select based on timeframe)
        
        Returns:
            Dict with trend analysis
        """
        if df is None or df.empty or len(df) < 10:
            return {
                'timeframe': timeframe,
                'trend': 'unknown',
                'ema': None,
                'price': None,
                'rsi': None,
                'valid': False
            }
        
        try:
            # Auto-select EMA period based on timeframe
            if ema_period is None:
                if timeframe == '1d':
                    ema_period = Config.EMA_HTF  # 100 for daily
                else:
                    ema_period = Config.EMA_LTF  # 21 for lower timeframes
            
            # Calculate indicators
            current_price = float(df['close'].iloc[-1])
            ema = TechnicalIndicators.calculate_ema(df['close'], ema_period)
            rsi = TechnicalIndicators.calculate_rsi(df['close'], Config.RSI_PERIOD)
            
            # Determine trend
            if current_price > ema:
                trend = 'bullish'
            elif current_price < ema:
                trend = 'bearish'
            else:
                trend = 'neutral'
            
            return {
                'timeframe': timeframe,
                'trend': trend,
                'ema': ema,
                'ema_period': ema_period,
                'price': current_price,
                'rsi': rsi,
                'valid': True
            }
            
        except Exception as e:
            print(f"Error analyzing {timeframe}: {e}")
            return {
                'timeframe': timeframe,
                'trend': 'unknown',
                'ema': None,
                'price': None,
                'rsi': None,
                'valid': False
            }
    
    def check_htf_trend(self, daily_df: pd.DataFrame) -> Dict:
        """
        Check Daily (HTF) trend - this is the primary filter
        
        Pine Script equivalent:
        dailyEma = request.security(syminfo.tickerid, "D", ta.ema(close, htfEmaLength))
        dailyClose = request.security(syminfo.tickerid, "D", close)
        
        Args:
            daily_df: Daily timeframe DataFrame
        
        Returns:
            Dict with HTF trend analysis
        """
        return self.analyze_timeframe(daily_df, '4h', Config.EMA_HTF)
    
    def analyze_cascade(self, timeframe_data: Dict[str, pd.DataFrame]) -> Dict:
        """
        Analyze full timeframe cascade: Daily → 4H → 2H → 1H → 30m
        
        Args:
            timeframe_data: Dict with DataFrames for each timeframe
                           {'1d': df, '4h': df, '2h': df, '1h': df, '30m': df}
        
        Returns:
            Dict with cascade analysis results
        """
        cascade_results = {}
        
        # Analyze each timeframe
        for tf in Config.CASCADE_TIMEFRAMES:
            if tf in timeframe_data and timeframe_data[tf] is not None:
                cascade_results[tf] = self.analyze_timeframe(timeframe_data[tf], tf)
            else:
                cascade_results[tf] = {
                    'timeframe': tf,
                    'trend': 'unknown',
                    'valid': False
                }
        
        # Check alignment
        valid_trends = [
            result['trend'] 
            for result in cascade_results.values() 
            if result['valid'] and result['trend'] != 'unknown'
        ]
        
        # All must be bullish or all must be bearish
        all_bullish = all(trend == 'bullish' for trend in valid_trends)
        all_bearish = all(trend == 'bearish' for trend in valid_trends)
        
        aligned = all_bullish or all_bearish
        
        if all_bullish:
            direction = 'long'
        elif all_bearish:
            direction = 'short'
        else:
            direction = 'mixed'
        
        return {
            'cascade': cascade_results,
            'aligned': aligned,
            'direction': direction,
            'valid_timeframes': len(valid_trends),
            'bullish_count': sum(1 for t in valid_trends if t == 'bullish'),
            'bearish_count': sum(1 for t in valid_trends if t == 'bearish')
        }
    
    def check_daily_alignment(self, daily_df: pd.DataFrame, signal_direction: str) -> Tuple[bool, Dict]:
        """
        Check if Daily timeframe aligns with intended signal direction
        
        Pine Script equivalent:
        longCondition := useHTF ? (longCondition and dailyClose > dailyEma) : longCondition
        shortCondition := useHTF ? (shortCondition and dailyClose < dailyEma) : shortCondition
        
        Args:
            daily_df: Daily timeframe DataFrame
            signal_direction: 'long' or 'short'
        
        Returns:
            Tuple of (aligned: bool, daily_analysis: dict)
        """
        daily_analysis = self.check_htf_trend(daily_df)
        
        if not daily_analysis['valid']:
            return False, daily_analysis
        
        # Check alignment
        if signal_direction == 'long':
            aligned = daily_analysis['trend'] == 'bullish'
        elif signal_direction == 'short':
            aligned = daily_analysis['trend'] == 'bearish'
        else:
            aligned = False
        
        return aligned, daily_analysis
    
    def get_cascade_summary(self, cascade_data: Dict) -> str:
        """
        Generate human-readable cascade summary
        
        Args:
            cascade_data: Cascade analysis results
        
        Returns:
            Formatted string summary
        """
        lines = []
        lines.append("Multi-Timeframe Cascade Analysis:")
        lines.append("=" * 40)
        
        for tf in Config.CASCADE_TIMEFRAMES:
            if tf in cascade_data['cascade']:
                result = cascade_data['cascade'][tf]
                if result['valid']:
                    trend_emoji = "🟢" if result['trend'] == 'bullish' else "🔴" if result['trend'] == 'bearish' else "⚪"
                    lines.append(
                        f"{trend_emoji} {tf.upper():>4}: {result['trend'].upper():>8} | "
                        f"Price: {result['price']:.2f} | EMA({result['ema_period']}): {result['ema']:.2f}"
                    )
                else:
                    lines.append(f"⚪ {tf.upper():>4}: NO DATA")
        
        lines.append("=" * 40)
        lines.append(f"Alignment: {'✅ ALL ALIGNED' if cascade_data['aligned'] else '❌ MIXED'}")
        lines.append(f"Direction: {cascade_data['direction'].upper()}")
        lines.append(f"Valid Timeframes: {cascade_data['valid_timeframes']}/{len(Config.CASCADE_TIMEFRAMES)}")
        
        return "\n".join(lines)
    
    def calculate_cascade_confidence(self, cascade_data: Dict) -> float:
        """
        Calculate confidence score based on cascade alignment
        
        Args:
            cascade_data: Cascade analysis results
        
        Returns:
            Confidence score (0-100)
        """
        if not cascade_data['aligned']:
            return 0.0
        
        # Base confidence from alignment
        base_confidence = 50.0
        
        # Bonus for each aligned timeframe
        valid_count = cascade_data['valid_timeframes']
        if valid_count > 0:
            alignment_bonus = (valid_count / len(Config.CASCADE_TIMEFRAMES)) * 30.0
        else:
            alignment_bonus = 0.0
        
        # Bonus for strong RSI alignment
        rsi_bonus = 0.0
        if cascade_data['direction'] == 'long':
            # Check how many timeframes have RSI > 50
            rsi_aligned = sum(
                1 for result in cascade_data['cascade'].values()
                if result.get('valid') and result.get('rsi') and result['rsi'] > Config.RSI_LONG_THRESHOLD
            )
            rsi_bonus = (rsi_aligned / len(Config.CASCADE_TIMEFRAMES)) * 20.0
        elif cascade_data['direction'] == 'short':
            # Check how many timeframes have RSI < 50
            rsi_aligned = sum(
                1 for result in cascade_data['cascade'].values()
                if result.get('valid') and result.get('rsi') and result['rsi'] < Config.RSI_SHORT_THRESHOLD
            )
            rsi_bonus = (rsi_aligned / len(Config.CASCADE_TIMEFRAMES)) * 20.0
        
        total_confidence = min(95.0, base_confidence + alignment_bonus + rsi_bonus)
        
        return round(total_confidence, 1)
