"""
Alert Formatter
Format trading alerts in dashboard-style for Telegram.
"""

from typing import Any, Dict
from datetime import datetime
from core.config import Config


_MD_ESCAPE_MAP = {
    "\\": "\\\\",
    "_": "\\_",
    "*": "\\*",
    "[": "\\[",
    "]": "\\]",
    "(": "\\(",
    ")": "\\)",
    "`": "\\`",
}


def _escape_markdown(value: Any) -> str:
    """Escape Telegram Markdown-sensitive characters in dynamic values."""

    if value is None:
        return ""

    text = str(value)
    for char, escaped in _MD_ESCAPE_MAP.items():
        text = text.replace(char, escaped)
    return text


def _format_price(value: Any, digits: int = 5) -> str:
    """Format price-like values safely for alert output."""

    if value is None:
        return "N/A"

    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


class AlertFormatter:
    """
    Format trading alerts for Telegram with rich, dashboard-style presentation.
    """
    
    @staticmethod
    def format_signal_alert(alert_data: Dict) -> str:
        """
        Format complete signal alert with all details
        
        Args:
            alert_data: Dictionary with signal information
        
        Returns:
            Formatted Markdown string for Telegram
        """
        signal = alert_data.get('signal', 'HOLD')
        raw_symbol = alert_data.get('symbol', 'UNKNOWN')
        symbol_display = _escape_markdown(raw_symbol)
        timeframe_value = alert_data.get('timeframe', '1h')
        timeframe_display = _escape_markdown(str(timeframe_value).upper())
        confidence = alert_data.get('confidence', 0)
        alert_type = alert_data.get('alert_type', 'NEW')

        # Signal emoji and direction
        if signal == 'LONG':
            emoji = '🟢'
            direction = 'LONG'
        elif signal == 'SHORT':
            emoji = '🔴'
            direction = 'SHORT'
        else:
            emoji = '⚪'
            direction = 'HOLD'

        # Alert type indicator
        type_indicator = '🚨 *NEW SIGNAL*' if alert_type == 'NEW' else '⚡ *CONTINUATION*'

        # Build message sections
        lines = []

        # Header
        lines.append(type_indicator)
        lines.append(f"{emoji} *{direction}: {symbol_display}* ({timeframe_display})")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("")

        # Entry Conditions Section
        if 'entry_analysis' in alert_data:
            entry = alert_data['entry_analysis']
            lines.append("📊 *ENTRY CONDITIONS*")

            if 'conditions_met' in entry:
                for condition, met in entry['conditions_met'].items():
                    icon = "✅" if met else "❌"
                    condition_name = _escape_markdown(condition.upper().replace('_', ' '))
                    lines.append(f"  {icon} {condition_name}")

            lines.append("")

            # Price and Indicators
            lines.append("💰 *PRICE LEVELS*")
            lines.append(f"  Current: *{entry.get('current_price', 0):.2f}*")
            lines.append(f"  EMA(21): {entry.get('ema_21', 0):.2f}")

            if signal == 'LONG':
                price_vs_ema = "↑ Above" if entry.get('above_ema') else "↓ Below"
            else:
                price_vs_ema = "↓ Below" if entry.get('below_ema') else "↑ Above"
            lines.append(f"  Position: {price_vs_ema} EMA")

            lines.append("")

            # RSI
            lines.append("📈 *MOMENTUM*")
            rsi_val = entry.get('rsi', 50)
            lines.append(f"  RSI(14): *{rsi_val:.1f}*")

            if rsi_val > 70:
                rsi_level = "Overbought"
            elif rsi_val < 30:
                rsi_level = "Oversold"
            elif rsi_val > 50:
                rsi_level = "Bullish"
            else:
                rsi_level = "Bearish"
            lines.append(f"  Level: {rsi_level}")

            lines.append("")

            # Daily HTF
            if entry.get('daily_price'):
                lines.append("🌍 *DAILY TIMEFRAME*")
                lines.append(f"  Price: {entry['daily_price']:.2f}")
                lines.append(f"  EMA(100): {entry['daily_ema_100']:.2f}")

                if entry.get('daily_bullish'):
                    daily_trend = "✅ BULLISH ↑"
                elif entry.get('daily_bearish'):
                    daily_trend = "✅ BEARISH ↓"
                else:
                    daily_trend = "⚠️ NEUTRAL"

                lines.append(f"  Trend: {daily_trend}")
                lines.append("")

        # Volume Section
        if 'volume_data' in alert_data:
            vol = alert_data['volume_data']
            lines.append("📊 *VOLUME ANALYSIS*")

            spike_icon = "✅ SPIKE" if vol.get('spike') else "❌ LOW"
            lines.append(f"  Status: {spike_icon}")
            lines.append(f"  Current: {vol.get('current_volume', 0):,.0f}")
            lines.append(f"  Average: {vol.get('average_volume', 0):,.0f}")
            lines.append(f"  Ratio: *{vol.get('ratio', 0):.2f}x*")

            lines.append("")

        # Multi-Timeframe Cascade
        if 'cascade' in alert_data:
            cascade = alert_data['cascade']
            lines.append("📈 *MULTI-TIMEFRAME CASCADE*")

            cascade_timeframes = ['1d', '4h', '2h', '1h', '30m']
            for tf in cascade_timeframes:
                if tf in cascade.get('cascade', {}):
                    tf_data = cascade['cascade'][tf]
                    if tf_data.get('valid'):
                        trend = tf_data['trend']
                        trend_emoji = "🟢" if trend == 'bullish' else "🔴" if trend == 'bearish' else "⚪"
                        lines.append(f"  {trend_emoji} {tf.upper():>4} → {trend.upper()}")

            lines.append("")

            # Alignment status
            if cascade.get('aligned'):
                lines.append("  ✅ *ALL TIMEFRAMES ALIGNED*")
            else:
                lines.append("  ⚠️ *MIXED TIMEFRAMES*")

            lines.append("")

        # Trigger details and trade plan
        trigger_context = alert_data.get('trigger_context') or {}
        triggered_by = alert_data.get('triggered_by')
        trigger_label = None

        if isinstance(trigger_context, dict):
            event_payload = trigger_context.get('event') or {}
            if isinstance(event_payload, dict):
                trigger_label = event_payload.get('event_type')
            if not trigger_label:
                trigger_label = trigger_context.get('type')

        if not trigger_label and isinstance(triggered_by, str):
            trigger_label = (
                triggered_by.split(':', 1)[1] if triggered_by.startswith('event:') else triggered_by
            )

        if not trigger_label:
            trigger_label = 'time'

        trigger_label = _escape_markdown(trigger_label)

        trade_levels = alert_data.get('trade_levels')
        if not isinstance(trade_levels, dict):
            trade_levels = {
                'entry_price': alert_data.get('entry_price'),
                'stop_loss': alert_data.get('stop_loss'),
                'take_profit': alert_data.get('take_profit'),
            }

        has_trade_levels = any(
            trade_levels.get(key) is not None for key in ['entry_price', 'stop_loss', 'take_profit']
        )

        lines.append("🎯 *TRIGGER DETAILS*")
        lines.append(f"  Triggered By: {trigger_label}")
        lines.append("")

        if has_trade_levels:
            lines.append("📌 *TRADE PLAN*")
            entry_fmt = _escape_markdown(_format_price(trade_levels.get('entry_price')))
            stop_fmt = _escape_markdown(_format_price(trade_levels.get('stop_loss')))
            take_fmt = _escape_markdown(_format_price(trade_levels.get('take_profit')))
            lines.append(f"  Entry: `{entry_fmt}`")
            lines.append(f"  Stop Loss: `{stop_fmt}`")
            lines.append(f"  Take Profit: `{take_fmt}`")
            lines.append("")

        # Confidence and Timestamp
        lines.append("━━━━━━━━━━━━━━━━━━━━")

        # Confidence bar
        confidence_bars = int(confidence / 10)
        confidence_bar = "█" * confidence_bars + "░" * (10 - confidence_bars)
        lines.append(f"⚡ *CONFIDENCE:* {confidence:.1f}%")
        lines.append(f"   {confidence_bar}")

        lines.append("")
        lines.append(f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        return "\n".join(lines)
    
    @staticmethod
    def format_compact_alert(alert_data: Dict) -> str:
        """
        Format compact alert (shorter version)
        
        Args:
            alert_data: Dictionary with signal information
        
        Returns:
            Formatted compact string
        """
        signal = alert_data.get('signal', 'HOLD')
        symbol = alert_data.get('symbol', 'UNKNOWN')
        timeframe = alert_data.get('timeframe', '1h')
        confidence = alert_data.get('confidence', 0)
        price = alert_data.get('price', 0)
        alert_type = alert_data.get('alert_type', 'NEW')
        
        emoji = '🟢' if signal == 'LONG' else '🔴' if signal == 'SHORT' else '⚪'
        type_icon = '🚨' if alert_type == 'NEW' else '⚡'
        
        message = f"{type_icon} {emoji} *{signal}: {symbol}* ({timeframe}) | Price: {price:.2f} | Confidence: {confidence:.0f}%"
        
        return message
    
    @staticmethod
    def format_startup_message() -> str:
        """
        Format bot startup message
        
        Returns:
            Formatted startup message
        """
        lines = []
        lines.append("🚀 *OptiCore Trading Bot Started*")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        lines.append("📊 *CONFIGURATION*")
        lines.append(f"  EMA: {Config.EMA_LTF}/{Config.EMA_HTF}")
        lines.append(f"  RSI: {Config.RSI_PERIOD}")
        lines.append(f"  Volume: {Config.VOLUME_MULTIPLIER}x")
        lines.append(f"  Engulfing: {'Strict' if Config.STRICT_ENGULFING else 'Relaxed'}")
        lines.append("")
        lines.append(f"⏱️  *TIMEFRAMES*")
        lines.append(f"  Entry: {', '.join(Config.ENTRY_TIMEFRAMES)}")
        lines.append(f"  HTF Filter: {Config.HTF_TIMEFRAME}")
        lines.append("")
        lines.append(f"📋 *WATCHLIST*")
        lines.append(f"  Symbols: {len(Config.WATCHLIST)}")
        lines.append(f"  {', '.join(list(Config.WATCHLIST.keys())[:5])}...")
        lines.append("")
        lines.append("✅ *Bot is monitoring markets...*")
        lines.append("")
        lines.append(f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_summary(summary_data: Dict) -> str:
        """
        Format daily/periodic summary
        
        Args:
            summary_data: Summary statistics
        
        Returns:
            Formatted summary message
        """
        lines = []
        lines.append("📊 *OptiCore Bot - Summary*")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        lines.append("🔔 *SIGNALS*")
        lines.append(f"  Total: {summary_data.get('total_signals', 0)}")
        lines.append(f"  🟢 Long: {summary_data.get('long_signals', 0)}")
        lines.append(f"  🔴 Short: {summary_data.get('short_signals', 0)}")
        lines.append("")
        
        if 'active_signals' in summary_data:
            active = summary_data['active_signals']
            lines.append("⚡ *ACTIVE SIGNALS*")
            lines.append(f"  Total: {active.get('total', 0)}")
            if active.get('by_symbol'):
                lines.append("  By Symbol:")
                for symbol, count in list(active.get('by_symbol', {}).items())[:5]:
                    lines.append(f"    • {symbol}: {count}")
            lines.append("")
        
        if 'efficiency' in summary_data:
            lines.append("⚡ *PERFORMANCE*")
            lines.append(f"  Efficiency: {summary_data.get('efficiency', 0):.1f}%")
            lines.append(f"  Avg Confidence: {summary_data.get('avg_confidence', 0):.1f}%")
            lines.append("")
        
        lines.append(f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_error(error_message: str) -> str:
        """
        Format error message
        
        Args:
            error_message: Error description
        
        Returns:
            Formatted error message
        """
        lines = []
        lines.append("⚠️ *OptiCore Bot - Error*")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        lines.append(error_message)
        lines.append("")
        lines.append(f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(lines)
