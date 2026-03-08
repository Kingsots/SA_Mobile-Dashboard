"""
OptiCore Strategy
Main strategy class matching Pine Script logic exactly.
"""

import pandas as pd
from typing import Dict, Tuple, Optional
from core.config import Config
from core.indicators import TechnicalIndicators
from core.multi_timeframe import MultiTimeframeAnalyzer
from .entry_rules import EntryRules
from .volume_filter import VolumeFilter


class OptiCoreStrategy:
    """
    OptiCore Trading Strategy
    
    Matches your Pine Script exactly:
    - EMA 21/100
    - RSI 14
    - Strict Engulfing
    - Volume Filter 1.2x
    - Daily HTF Trend Filter
    - Multi-Timeframe Cascade Alignment
    """
    
    def __init__(self):
        """Initialize OptiCore strategy"""
        self.config = Config()
        self.entry_rules = EntryRules(strict_engulfing=Config.STRICT_ENGULFING)
        self.mtf_analyzer = MultiTimeframeAnalyzer()
    
    def analyze_symbol(self, symbol: str, timeframe: str, 
                      timeframe_data: Dict[str, pd.DataFrame]) -> Dict:
        """
        Analyze a symbol across all timeframes
        
        Args:
            symbol: Trading symbol
            timeframe: Entry timeframe ('30m' or '1h')
            timeframe_data: Dict with all timeframe DataFrames
                           {'1d': df, '4h': df, '2h': df, '1h': df, '30m': df}
        
        Returns:
            Complete analysis dictionary with signal and all data
        """
        result = {
            'symbol': symbol,
            'timeframe': timeframe,
            'signal': 'HOLD',
            'confidence': 0.0,
            'entry_valid': False,
            'timestamp': pd.Timestamp.now()
        }
        
        try:
            # Get current and daily timeframes
            current_df = timeframe_data.get(timeframe)
            daily_df = timeframe_data.get('1d')
            
            if current_df is None or current_df.empty:
                result['error'] = f'No data for {timeframe}'
                return result
            
            # 1. Check entry conditions on current timeframe
            signal, entry_analysis = self.entry_rules.check_entry(current_df, daily_df)
            
            result['signal'] = signal
            result['entry_analysis'] = entry_analysis
            result['entry_valid'] = entry_analysis.get('entry_valid', False)
            
            if signal != 'HOLD':
                # 2. Analyze multi-timeframe cascade
                cascade_data = self.mtf_analyzer.analyze_cascade(timeframe_data)
                result['cascade'] = cascade_data
                
                # 3. Check if cascade aligns with signal
                cascade_aligned = cascade_data['aligned'] and cascade_data['direction'] == signal.lower()
                result['cascade_aligned'] = cascade_aligned
                
                # 4. Calculate final confidence
                entry_confidence = entry_analysis.get('confidence', 0)
                cascade_confidence = self.mtf_analyzer.calculate_cascade_confidence(cascade_data)
                
                # Weighted average: 60% entry conditions, 40% cascade alignment
                final_confidence = (entry_confidence * 0.6) + (cascade_confidence * 0.4)
                result['confidence'] = round(final_confidence, 1)
                
                # 5. Get current price and indicators
                result['price'] = float(current_df['close'].iloc[-1])
                result['indicators'] = TechnicalIndicators.calculate_all_indicators(
                    current_df, 
                    Config.EMA_LTF, 
                    Config.RSI_PERIOD
                )
                
                # 6. Volume analysis
                volume_spike, volume_data = VolumeFilter.check_volume_spike(current_df)
                result['volume_data'] = volume_data
            
            else:
                # HOLD signal - still provide some data
                result['price'] = float(current_df['close'].iloc[-1]) if not current_df.empty else 0
                result['indicators'] = TechnicalIndicators.calculate_all_indicators(
                    current_df,
                    Config.EMA_LTF,
                    Config.RSI_PERIOD
                )
        
        except Exception as e:
            result['error'] = str(e)
            print(f"❌ Strategy analysis error for {symbol} {timeframe}: {e}")
        
        return result
    
    def should_send_alert(self, result: Dict) -> Tuple[bool, str]:
        """
        Determine if an alert should be sent
        
        Args:
            result: Analysis result dictionary
        
        Returns:
            Tuple of (should_alert: bool, alert_type: str)
            alert_type: 'NEW' or 'CONTINUATION'
        """
        # Don't alert on HOLD signals
        if result['signal'] == 'HOLD':
            return False, ''
        
        # Don't alert if confidence is too low
        if result['confidence'] < 50.0:
            return False, ''
        
        # Alert on valid entries
        if result['entry_valid']:
            # Check if this is a new signal or continuation
            # This would be determined by signal tracker (implemented later)
            return True, 'NEW'
        
        # Alert on continuation if volume spike occurs
        if result.get('volume_data', {}).get('spike', False):
            return True, 'CONTINUATION'
        
        return False, ''
    
    def format_signal_summary(self, result: Dict) -> str:
        """
        Format analysis result as readable summary
        
        Args:
            result: Analysis result dictionary
        
        Returns:
            Formatted string summary
        """
        if 'error' in result:
            return f"❌ Error analyzing {result['symbol']}: {result['error']}"
        
        lines = []
        
        # Header
        signal_emoji = "🟢" if result['signal'] == 'LONG' else "🔴" if result['signal'] == 'SHORT' else "⚪"
        lines.append("=" * 60)
        lines.append(f"{signal_emoji} {result['signal']} - {result['symbol']} ({result['timeframe']})")
        lines.append("=" * 60)
        
        # Entry conditions
        if 'entry_analysis' in result:
            entry = result['entry_analysis']
            lines.append("")
            lines.append("📊 Entry Conditions:")
            
            if 'conditions_met' in entry:
                for condition, met in entry['conditions_met'].items():
                    icon = "✅" if met else "❌"
                    lines.append(f"  {icon} {condition.upper()}")
            
            lines.append(f"  Price: {entry.get('current_price', 0):.2f}")
            lines.append(f"  EMA(21): {entry.get('ema_21', 0):.2f}")
            lines.append(f"  RSI(14): {entry.get('rsi', 0):.1f}")
            
            if entry.get('daily_price'):
                daily_trend = "BULLISH" if entry.get('daily_bullish') else "BEARISH"
                lines.append(f"  Daily: {entry['daily_price']:.2f} ({daily_trend})")
        
        # Volume
        if 'volume_data' in result:
            vol = result['volume_data']
            strength = VolumeFilter.get_volume_strength(vol['ratio'])
            spike_icon = "✅" if vol['spike'] else "❌"
            lines.append("")
            lines.append(f"📊 Volume: {spike_icon} {strength} ({vol['ratio']:.2f}x average)")
        
        # Multi-timeframe cascade
        if 'cascade' in result:
            cascade = result['cascade']
            lines.append("")
            lines.append("📈 Multi-Timeframe Cascade:")
            
            for tf in Config.CASCADE_TIMEFRAMES:
                if tf in cascade['cascade']:
                    tf_data = cascade['cascade'][tf]
                    if tf_data['valid']:
                        trend_emoji = "🟢" if tf_data['trend'] == 'bullish' else "🔴"
                        lines.append(
                            f"  {trend_emoji} {tf.upper():>4}: {tf_data['trend'].upper()} "
                            f"(Price: {tf_data['price']:.2f}, EMA: {tf_data['ema']:.2f})"
                        )
            
            alignment_icon = "✅" if cascade['aligned'] else "❌"
            lines.append(f"  {alignment_icon} Alignment: {'ALL ALIGNED' if cascade['aligned'] else 'MIXED'}")
        
        # Confidence
        lines.append("")
        lines.append(f"⚡ Confidence: {result['confidence']:.1f}%")
        lines.append(f"🕒 Time: {result['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def get_strategy_info(self) -> str:
        """
        Get strategy configuration information
        
        Returns:
            Strategy info string
        """
        lines = []
        lines.append("OptiCore Trading Strategy")
        lines.append("=" * 60)
        lines.append(f"EMA Periods: LTF={Config.EMA_LTF}, HTF={Config.EMA_HTF}")
        lines.append(f"RSI Period: {Config.RSI_PERIOD}")
        lines.append(f"Volume Filter: {Config.VOLUME_MULTIPLIER}x (Period: {Config.VOLUME_PERIOD})")
        lines.append(f"Strict Engulfing: {Config.STRICT_ENGULFING}")
        lines.append(f"Entry Timeframes: {', '.join(Config.ENTRY_TIMEFRAMES)}")
        lines.append(f"HTF Filter: {Config.HTF_TIMEFRAME} (Daily)")
        lines.append(f"Cascade Timeframes: {' → '.join(Config.CASCADE_TIMEFRAMES)}")
        lines.append("=" * 60)
        
        return "\n".join(lines)
