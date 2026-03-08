"""
OptiCore Scheduler
Run the OptiCore bot automatically on configured intervals.
"""

import time
import threading
from datetime import datetime
from typing import Dict
import schedule
from core.config import Config
from utils.logger import setup_logger
from main_bot import OptiCoreBot


class OptiCoreScheduler:
    """Schedule recurring OptiCoreBot executions for each entry timeframe."""

    def __init__(self, force_refresh: bool = False):
        self.logger = setup_logger('OptiCoreScheduler')
        self.bot = OptiCoreBot()
        self.force_refresh = force_refresh
        self._lock = threading.Lock()
        self._running = False
        self._jobs = []

    def _register_jobs(self):
        """Register schedule jobs using Config.SCHEDULER_INTERVALS."""
        schedule.clear()
        self._jobs.clear()

        intervals: Dict[str, int] = Config.SCHEDULER_INTERVALS
        for timeframe, minutes in intervals.items():
            job = schedule.every(minutes).minutes.do(self._run_timeframe_job, timeframe)
            self._jobs.append(job)
            self.logger.info(
                "Scheduled %s run every %d minutes", timeframe, minutes
            )

    def _run_timeframe_job(self, timeframe: str):
        """Execute a single timeframe run thread-safely."""
        if not self._running:
            return

        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            self.logger.warning("Previous run still in progress. Skipping %s", timeframe)
            return

        try:
            self.logger.info("Starting scheduled run | timeframe=%s", timeframe)
            summary = self.bot.run(timeframes=[timeframe], force_refresh=self.force_refresh)
            self._log_summary(timeframe, summary)
        except Exception as exc:  # pragma: no cover - defensive guard
            self.logger.error("Scheduler run failure (%s): %s", timeframe, exc)
        finally:
            self._lock.release()

    def _log_summary(self, timeframe: str, summary: Dict):
        """Send concise summary to the log."""
        if not summary:
            return
        if summary.get('status') == 'config_error':
            self.logger.error("Config validation failed: %s", summary.get('errors'))
            return

        signals_sent = summary.get('signals_sent', 0)
        long_signals = summary.get('long_signals', 0)
        short_signals = summary.get('short_signals', 0)
        skipped_alignment = summary.get('skipped_alignment', 0)
        skipped_confidence = summary.get('skipped_confidence', 0)

        self.logger.info(
            "Finished run | tf=%s sent=%d long=%d short=%d skipped(alignment=%d, confidence=%d)",
            timeframe,
            signals_sent,
            long_signals,
            short_signals,
            skipped_alignment,
            skipped_confidence
        )

    def start(self):
        """Start the scheduler loop."""
        if self._running:
            self.logger.warning("Scheduler already running")
            return

        valid, errors = Config.validate_config()
        if not valid:
            for error in errors:
                self.logger.error(error)
            raise RuntimeError("Invalid configuration. See log for details.")

        self.logger.info("OptiCore Scheduler starting at %s", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        self._register_jobs()
        self._running = True

        try:
            while self._running:
                schedule.run_pending()
                time.sleep(5)
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received. Stopping scheduler...")
        finally:
            self.stop()

    def stop(self):
        """Stop all jobs and exit the loop."""
        if not self._running:
            return

        self._running = False
        schedule.clear()
        self._jobs.clear()
        self.logger.info("Scheduler stopped")

    def run_once(self):
        """Run all configured timeframes immediately (one-shot)."""
        self.logger.info("Running one-shot execution for all timeframes")
        valid, errors = Config.validate_config()
        if not valid:
            for error in errors:
                self.logger.error(error)
            raise RuntimeError("Invalid configuration. See log for details.")

        for timeframe in Config.ENTRY_TIMEFRAMES:
            self._run_timeframe_job(timeframe)


if __name__ == '__main__':
    scheduler = OptiCoreScheduler()
    scheduler.start()
