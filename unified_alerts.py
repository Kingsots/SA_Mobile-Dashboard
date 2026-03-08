"""
Unified Alert System
Combines OptiCore strategy signals with ML predictions
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json

from core.config import Config
from core.database import DatabaseManager
from strategies.opticore_strategy import OptiCoreStrategy
from signals.xgb_signal_engine import XGBSignalEngine
from alerts.telegram_bot import TelegramBot
from alerts.formatter import AlertFormatter


class SignalConsensus:
    """
    Signal consensus logic
    
    Combines signals from:
    1. OptiCore strategy (rule-based)
    2. XGBoost ML model (data-driven)
    
    Consensus levels:
    - STRONG: Both agree (OptiCore + ML same direction)
    - MODERATE: One signal, other neutral
    - WEAK: Contradicting signals
    """
    
    @staticmethod
    def calculate_consensus(
        opticore_signal: Optional[str],
        ml_signal: Optional[int],
        ml_confidence: float = 0.0
    ) -> Dict:
        """
        Calculate signal consensus
        
        Args:
            opticore_signal: 'long', 'short', or None
            ml_signal: 1 (BUY), -1 (SELL), 0 (NEUTRAL), or None
            ml_confidence: ML prediction confidence
            
        Returns:
            Dict with consensus result
        """
        # Map OptiCore to numeric
        opticore_numeric = {
            'long': 1,
            'short': -1,
            None: 0
        }.get(opticore_signal, 0)
        
        # Handle missing signals
        if ml_signal is None:
            ml_signal = 0
        
        # Calculate consensus
        if opticore_numeric == ml_signal and opticore_numeric != 0:
            # Both agree on direction
            level = 'STRONG'
            direction = 'BUY' if opticore_numeric == 1 else 'SELL'
            confidence = (100 + ml_confidence * 100) / 2  # Average of 100% and ML confidence
        
        elif opticore_numeric != 0 and ml_signal == 0:
            # OptiCore signal, ML neutral
            level = 'MODERATE'
            direction = 'BUY' if opticore_numeric == 1 else 'SELL'
            confidence = 75.0  # Moderate confidence
        
        elif opticore_numeric == 0 and ml_signal != 0:
            # ML signal, OptiCore neutral
            level = 'MODERATE'
            direction = 'BUY' if ml_signal == 1 else 'SELL'
            confidence = ml_confidence * 100
        
        elif opticore_numeric != 0 and ml_signal != 0 and opticore_numeric != ml_signal:
            # Contradicting signals
            level = 'WEAK'
            direction = 'CONFLICTING'
            confidence = 30.0  # Low confidence
        
        else:
            # Both neutral
            level = 'NONE'
            direction = 'NEUTRAL'
            confidence = 0.0
        
        return {
            'level': level,
            'direction': direction,
            'confidence': confidence,
            'opticore_signal': opticore_signal,
            'ml_signal': Config.ML_SIGNAL_LABELS.get(ml_signal, 'NEUTRAL'),
            'ml_confidence': ml_confidence * 100 if ml_confidence else 0.0
        }


class UnifiedAlertSystem:
    """
    Unified alert system combining OptiCore and ML signals
    
    Alert triggers:
    1. STRONG consensus (both agree)
    2. MODERATE consensus (optional, configurable)
    3. Individual signals (OptiCore or ML only)
    """
    
    def __init__(self, alert_moderate: bool = True, alert_weak: bool = False):
        """
        Initialize unified alert system
        
        Args:
            alert_moderate: Send alerts for moderate consensus
            alert_weak: Send alerts for weak/conflicting signals
        """
        self.db = DatabaseManager()
        self.opticore = OptiCoreStrategy()
        self.ml_engine = XGBSignalEngine() if Config.USE_TIINGO_PIPELINE else None
        self.telegram = TelegramBot()
        self.formatter = AlertFormatter()
        
        self.alert_moderate = alert_moderate
        self.alert_weak = alert_weak
    
    def analyze_symbol(
        self, 
        symbol: str, 
        timeframe: str
    ) -> Optional[Dict]:
        """
        Analyze symbol with both OptiCore and ML
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe to analyze
            
        Returns:
            Dict with analysis results or None
        """
        results = {
            'symbol': symbol,
            'timeframe': timeframe,
            'timestamp': datetime.now().isoformat(),
            'opticore': None,
            'ml': None,
            'consensus': None
        }
        
        # 1. Run OptiCore strategy
        try:
            opticore_result = self.opticore.analyze(symbol, timeframe)
            
            if opticore_result and opticore_result.get('signal') != 'hold':
                results['opticore'] = {
                    'signal': opticore_result['signal'],
                    'confidence': opticore_result['confidence'],
                    'entry_price': opticore_result.get('entry_price'),
                    'indicators': opticore_result.get('indicators'),
                    'cascade': opticore_result.get('cascade_alignment')
                }
        except Exception as e:
            print(f"⚠️  OptiCore analysis failed for {symbol}: {e}")
        
        # 2. Run ML prediction (if enabled)
        if self.ml_engine:
            try:
                ml_result = self.ml_engine.generate_signal(symbol, timeframe)
                
                if ml_result:
                    results['ml'] = {
                        'signal': ml_result['signal'],
                        'signal_label': ml_result['signal_label'],
                        'confidence': ml_result['confidence'],
                        'model_version': ml_result['model_version']
                    }
            except Exception as e:
                print(f"⚠️  ML prediction failed for {symbol}: {e}")
        
        # 3. Calculate consensus
        opticore_signal = results['opticore']['signal'] if results['opticore'] else None
        ml_signal = results['ml']['signal'] if results['ml'] else None
        ml_confidence = results['ml']['confidence'] if results['ml'] else 0.0
        
        consensus = SignalConsensus.calculate_consensus(
            opticore_signal,
            ml_signal,
            ml_confidence
        )
        
        results['consensus'] = consensus
        
        return results
    
    def should_send_alert(self, analysis: Dict) -> bool:
        """
        Determine if alert should be sent
        
        Args:
            analysis: Analysis results
            
        Returns:
            True if alert should be sent
        """
        consensus = analysis['consensus']
        level = consensus['level']
        
        if level == 'STRONG':
            return True  # Always alert on strong consensus
        
        if level == 'MODERATE' and self.alert_moderate:
            return True
        
        if level == 'WEAK' and self.alert_weak:
            return True
        
        return False
    
    def format_unified_alert(self, analysis: Dict) -> str:
        """
        Format unified alert message
        
        Args:
            analysis: Analysis results
            
        Returns:
            Formatted Telegram message
        """
        symbol = analysis['symbol']
        timeframe = analysis['timeframe']
        consensus = analysis['consensus']
        opticore = analysis['opticore']
        ml = analysis['ml']
        
        # Emoji based on consensus level
        level_emoji = {
            'STRONG': '🔥',
            'MODERATE': '⚡',
            'WEAK': '⚠️',
            'NONE': '⚪'
        }
        
        # Direction emoji
        direction_emoji = {
            'BUY': '🟢',
            'SELL': '🔴',
            'NEUTRAL': '⚪',
            'CONFLICTING': '🟡'
        }
        
        emoji = level_emoji.get(consensus['level'], '⚪')
        dir_emoji = direction_emoji.get(consensus['direction'], '⚪')
        
        # Build message
        message = f"{emoji} **{consensus['level']} CONSENSUS**\n\n"
        message += f"**Symbol:** {symbol}\n"
        message += f"**Timeframe:** {timeframe}\n"
        message += f"**Direction:** {dir_emoji} {consensus['direction']}\n"
        message += f"**Confidence:** {consensus['confidence']:.0f}%\n\n"
        
        # OptiCore section
        message += f"📊 **OptiCore Strategy**\n"
        if opticore:
            message += f"   Signal: {opticore['signal'].upper()}\n"
            message += f"   Confidence: {opticore['confidence']:.0f}%\n"
            message += f"   Entry: {opticore.get('entry_price', 'N/A')}\n"
            
            if opticore.get('cascade'):
                aligned = opticore['cascade'].get('all_aligned', False)
                message += f"   Cascade: {'✅ Aligned' if aligned else '❌ Not aligned'}\n"
        else:
            message += f"   No signal\n"
        
        # ML section
        message += f"\n🤖 **ML Prediction**\n"
        if ml:
            message += f"   Signal: {ml['signal_label']}\n"
            message += f"   Confidence: {ml['confidence']:.1%}\n"
            message += f"   Model: {ml['model_version']}\n"
        else:
            message += f"   {'Not enabled' if not self.ml_engine else 'No prediction'}\n"
        
        # Recommendation
        message += f"\n💡 **Recommendation**\n"
        if consensus['level'] == 'STRONG':
            message += f"   {dir_emoji} Strong {consensus['direction']} signal - High confidence trade\n"
        elif consensus['level'] == 'MODERATE':
            message += f"   {dir_emoji} Moderate {consensus['direction']} signal - Consider entry\n"
        elif consensus['level'] == 'WEAK':
            message += f"   🟡 Conflicting signals - Wait for clarity\n"
        else:
            message += f"   ⚪ No actionable signal\n"
        
        message += f"\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return message
    
    def scan_and_alert(self, timeframes: List[str] = None, symbols: List[str] = None):
        """
        Scan all symbols and send alerts
        
        Args:
            timeframes: Timeframes to scan (default: ['30m', '1h'])
            symbols: Symbols to scan (default: all watchlist)
        """
        if timeframes is None:
            timeframes = Config.ENTRY_TIMEFRAMES
        
        if symbols is None:
            symbols = Config.get_symbol_list()
        
        print(f"\n{'='*70}")
        print(f"  🔍 UNIFIED ALERT SCAN")
        print(f"  Timeframes: {', '.join(timeframes)}")
        print(f"  Symbols: {len(symbols)}")
        print(f"{'='*70}\n")
        
        alerts_sent = 0
        
        for timeframe in timeframes:
            print(f"\n📊 Scanning {timeframe} timeframe...")
            
            for i, symbol in enumerate(symbols, 1):
                print(f"   [{i}/{len(symbols)}] {symbol:10}", end=' ')
                
                # Analyze symbol
                analysis = self.analyze_symbol(symbol, timeframe)
                
                if analysis is None:
                    print(f"⚠️  Analysis failed")
                    continue
                
                consensus = analysis['consensus']
                
                # Print result
                level_short = consensus['level'][0]  # S, M, W, N
                print(f"{level_short} {consensus['direction']:12} ({consensus['confidence']:5.1f}%)")
                
                # Send alert if needed
                if self.should_send_alert(analysis):
                    message = self.format_unified_alert(analysis)
                    
                    try:
                        self.telegram.send_message(message)
                        alerts_sent += 1
                        print(f"      ✅ Alert sent")
                    except Exception as e:
                        print(f"      ❌ Alert failed: {e}")
        
        print(f"\n{'='*70}")
        print(f"  ✅ Scan complete - {alerts_sent} alerts sent")
        print(f"{'='*70}\n")


def main():
    """Test unified alert system"""
    # Create unified system
    system = UnifiedAlertSystem(
        alert_moderate=True,   # Alert on moderate consensus
        alert_weak=False       # Don't alert on conflicting signals
    )
    
    # Test single symbol
    print("Testing single symbol analysis...")
    analysis = system.analyze_symbol('EURUSD', '1h')
    
    if analysis:
        print(f"\n✅ Analysis complete:")
        print(f"   Consensus: {analysis['consensus']['level']} - {analysis['consensus']['direction']}")
        print(f"   Confidence: {analysis['consensus']['confidence']:.1f}%")
        
        # Show formatted alert
        message = system.format_unified_alert(analysis)
        print(f"\n📱 Alert Message:")
        print(message)
    
    # Run full scan (uncomment to test)
    # system.scan_and_alert(timeframes=['1h'], symbols=['EURUSD', 'GBPUSD', 'USDJPY'])


if __name__ == '__main__':
    main()
