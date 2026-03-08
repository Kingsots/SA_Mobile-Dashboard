"""
OptiCore Main Bot
Coordinate data fetching, strategy evaluation, and alert delivery.
"""

from typing import Dict, List, Optional
from datetime import datetime
import traceback
from core.config import Config
from core.database import DatabaseManager
from data.fetcher import DataFetcher
from strategies.opticore_strategy import OptiCoreStrategy
from alerts.telegram_bot import TelegramBot
from alerts.signal_tracker import SignalTracker
from utils.logger import setup_logger


class OptiCoreBot:
    """Run the OptiCore strategy across the watchlist and manage alerts."""

    def __init__(self, min_confidence: Optional[float] = None):
        self.logger = setup_logger('OptiCoreBot')
        self.fetcher = DataFetcher()
        self.strategy = OptiCoreStrategy()
        self.telegram = TelegramBot()
        self.signal_tracker = SignalTracker()
        self.db = DatabaseManager()
        self.min_confidence = min_confidence if min_confidence is not None else Config.TARGET_EFFICIENCY * 100.0
        self.logger.info(
            "OptiCoreBot ready | min_confidence=%.1f", 
            self.min_confidence
        )

    def run(self, timeframes: Optional[List[str]] = None, symbols: Optional[List[str]] = None,
            force_refresh: bool = False) -> Dict:
        """Execute the strategy for the given symbols and timeframes."""
        valid, errors = Config.validate_config()
        if not valid:
            for error in errors:
                self.logger.error(error)
            return {'status': 'config_error', 'errors': errors}

        self.signal_tracker.cleanup_old_signals()

        timeframes = timeframes or Config.ENTRY_TIMEFRAMES
        symbols = symbols or Config.get_symbol_list()

        summary = {
            'total_processed': 0,
            'signals_evaluated': 0,
            'signals_sent': 0,
            'long_signals': 0,
            'short_signals': 0,
            'hold_count': 0,
            'skipped_alignment': 0,
            'skipped_confidence': 0,
            'errors': [],
            'confidence_values': []
        }

        self.logger.info("Running OptiCoreBot for %d symbols | timeframes=%s", len(symbols), ','.join(timeframes))

        for symbol in symbols:
            try:
                timeframe_data = self.fetcher.fetch_all_timeframes(symbol, Config.CASCADE_TIMEFRAMES, force_refresh)
                if not timeframe_data:
                    self.logger.warning("No data fetched for %s", symbol)
                    summary['errors'].append(f"Missing data for {symbol}")
                    continue

                for timeframe in timeframes:
                    result = self._analyze_symbol(symbol, timeframe, timeframe_data)
                    summary['total_processed'] += 1

                    if result is None:
                        continue

                    if 'error' in result:
                        summary['errors'].append(f"{symbol} {timeframe}: {result['error']}")
                        continue

                    if result['signal'] == 'HOLD':
                        summary['hold_count'] += 1
                        continue

                    summary['signals_evaluated'] += 1
                    summary['confidence_values'].append(result['confidence'])

                    if result['signal'] == 'LONG':
                        summary['long_signals'] += 1
                    elif result['signal'] == 'SHORT':
                        summary['short_signals'] += 1

                    if result.get('alert_sent'):
                        summary['signals_sent'] += 1
                    elif result.get('skip_reason') == 'alignment':
                        summary['skipped_alignment'] += 1
                    elif result.get('skip_reason') == 'confidence':
                        summary['skipped_confidence'] += 1

            except Exception as exc:  # pragma: no cover - defensive logging
                self.logger.error("Unhandled error for %s: %s", symbol, exc)
                self.logger.debug(traceback.format_exc())
                summary['errors'].append(f"{symbol}: {exc}")

        self._send_summary(summary)
        return summary

    def _analyze_symbol(self, symbol: str, timeframe: str, timeframe_data: Dict[str, object]) -> Optional[Dict]:
        """Analyze a single symbol/timeframe; return result with alert metadata."""
        if timeframe not in timeframe_data or timeframe_data[timeframe] is None:
            self.logger.debug("Missing %s data for %s", timeframe, symbol)
            return None
        if timeframe_data[timeframe].empty:
            self.logger.debug("Empty %s data for %s", timeframe, symbol)
            return None

        result = self.strategy.analyze_symbol(symbol, timeframe, timeframe_data)

        if 'error' in result:
            self.logger.error("Strategy error %s %s: %s", symbol, timeframe, result['error'])
            return result

        if result['signal'] == 'HOLD' or not result.get('entry_valid', False):
            self.signal_tracker.clear_signal(symbol, timeframe)
            return result

        if not result.get('cascade_aligned', False):
            self.logger.info("Cascade misalignment | %s %s", symbol, timeframe)
            result['skip_reason'] = 'alignment'
            self.signal_tracker.clear_signal(symbol, timeframe)
            return result

        if result['confidence'] < self.min_confidence:
            self.logger.info(
                "Low confidence %.1f%% < %.1f%% | %s %s",
                result['confidence'],
                self.min_confidence,
                symbol,
                timeframe
            )
            result['skip_reason'] = 'confidence'
            self.signal_tracker.clear_signal(symbol, timeframe)
            return result

        should_send, alert_type = self.signal_tracker.should_send_alert(symbol, timeframe, result['signal'])

        if not should_send:
            result['skip_reason'] = 'tracker'
            self.signal_tracker.update_signal(symbol, timeframe, result['signal'], result['confidence'], result.get('price', 0.0), send_alert=False)
            return result

        alert_payload = self._build_alert_payload(result, alert_type)
        sent = self.telegram.send_alert(alert_payload)
        result['alert_sent'] = sent
        result['alert_type'] = alert_type

        self.signal_tracker.update_signal(symbol, timeframe, result['signal'], result['confidence'], result.get('price', 0.0), send_alert=sent)

        if sent:
            self.db.save_signal(
                symbol,
                timeframe,
                result['signal'].lower(),
                result['confidence'],
                result.get('price', 0.0),
                result.get('indicators'),
                result.get('cascade')
            )
            self.logger.info("Alert sent | %s %s %s %.1f%%", alert_type, symbol, timeframe, result['confidence'])
        else:
            self.logger.warning("Alert failed | %s %s %s", alert_type, symbol, timeframe)

        return result

    def _build_alert_payload(self, result: Dict, alert_type: str) -> Dict:
        """Compose the dictionary consumed by AlertFormatter/TelegramBot."""
        payload = {
            'symbol': result['symbol'],
            'signal': result['signal'],
            'timeframe': result['timeframe'],
            'confidence': result['confidence'],
            'price': result.get('price', 0.0),
            'alert_type': alert_type,
            'entry_analysis': result.get('entry_analysis', {}),
            'volume_data': result.get('volume_data', {}),
            'cascade': result.get('cascade', {}),
            'timestamp': result.get('timestamp', datetime.utcnow()).isoformat()
        }
        return payload

    def _send_summary(self, summary: Dict):
        """Send a Telegram summary when we delivered at least one alert."""
        if not Config.SHOW_METRICS_IN_ALERTS:
            return

        if summary['signals_sent'] == 0:
            return

        avg_conf = sum(summary['confidence_values']) / len(summary['confidence_values']) if summary['confidence_values'] else 0.0
        efficiency = (summary['signals_sent'] / summary['signals_evaluated'] * 100.0) if summary['signals_evaluated'] else 0.0

        summary_data = {
            'total_signals': summary['signals_sent'],
            'long_signals': summary['long_signals'],
            'short_signals': summary['short_signals'],
            'efficiency': round(efficiency, 1),
            'avg_confidence': round(avg_conf, 1),
            'active_signals': self.signal_tracker.get_active_signals_summary()
        }

        self.telegram.send_summary(summary_data)


if __name__ == '__main__':
    bot = OptiCoreBot()
    run_summary = bot.run()
    print("Run Summary:")
    for key, value in run_summary.items():
        if key == 'confidence_values':
            continue
        print(f"  {key}: {value}")
