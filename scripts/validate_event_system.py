"""Validation utilities for the event-driven signal system."""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Tuple

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.config import Config

EVENT_LOG_PATH = Path("logs/event_debug.log")


def _load_recent_signals(limit: int = 50) -> pd.DataFrame:
    connection = sqlite3.connect(Config.DB_PATH)
    try:
        query = (
            "SELECT timestamp, ticker, signal, confidence, model_version, triggered_by "
            "FROM ml_signals ORDER BY timestamp DESC LIMIT ?"
        )
        df = pd.read_sql_query(query, connection, params=(limit,))
    finally:
        connection.close()

    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df


def _summarize_trigger_sources(df: pd.DataFrame) -> None:
    if df.empty:
        print("⚠️  No signal records found in ml_signals")
        return

    missing = df["triggered_by"].isna().sum()
    if missing:
        print(f"❌ Found {missing} signals with missing triggered_by values")
    else:
        print("✅ All inspected signals include triggered_by metadata")

    counts = Counter(df["triggered_by"].fillna("<missing>"))
    print("📊 Trigger source distribution (most recent records):")
    for source, count in counts.most_common():
        print(f"   • {source}: {count}")


def _parse_event_log() -> List[Tuple[datetime, dict]]:
    if not EVENT_LOG_PATH.exists():
        print(f"⚠️  Event log not found at {EVENT_LOG_PATH}")
        return []

    entries: List[Tuple[datetime, dict]] = []
    with EVENT_LOG_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue

            try:
                _, payload_str = line.split(" - ", 1)
                payload = json.loads(payload_str)
            except (ValueError, json.JSONDecodeError):
                continue

            timestamp_str = payload.get("timestamp")
            if timestamp_str:
                try:
                    entry_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                except ValueError:
                    entry_time = None
            else:
                entry_time = None

            entries.append((entry_time, payload))

    return entries


def _check_cooldowns(entries: Iterable[Tuple[datetime, dict]], window_minutes: int = 60) -> None:
    cutoff_delta = timedelta(minutes=window_minutes)
    symbol_events: defaultdict[str, List[datetime]] = defaultdict(list)

    for entry_time, payload in entries:
        if entry_time is None:
            continue
        event = payload.get("event") or {}
        symbol = event.get("ticker") or payload.get("symbol")
        phase = payload.get("phase")
        if not symbol or phase not in {"event_signal_generated", "event_signal_persisted"}:
            continue
        symbol_events[symbol].append(entry_time)

    violations = []
    for symbol, times in symbol_events.items():
        times.sort()
        for first, second in zip(times, times[1:]):
            if (second - first) < cutoff_delta:
                violations.append((symbol, first, second))

    if not violations:
        print("✅ No cooldown violations detected in event log")
    else:
        print("❌ Cooldown discrepancies detected:")
        for symbol, first, second in violations:
            delta = (second - first).total_seconds() / 60
            print(
                f"   • {symbol}: {delta:.1f} minutes between events at "
                f"{first.isoformat()} and {second.isoformat()}"
            )


def _print_recent_events(entries: List[Tuple[datetime, dict]], limit: int = 10) -> None:
    if not entries:
        print("⚠️  No event log entries available")
        return

    print("📝 Recent event log entries:")
    for entry_time, payload in entries[-limit:]:
        time_str = entry_time.isoformat() if entry_time else "<unknown>"
        phase = payload.get("phase", "<no phase>")
        event = payload.get("event", {})
        ticker = event.get("ticker", payload.get("ticker", "?"))
        event_type = event.get("event_type", payload.get("event_type", "?"))
        print(f"   • {time_str} | {ticker} | {phase} | {event_type}")


def main() -> None:
    print("=== Trigger Metadata Verification ===")
    df_signals = _load_recent_signals()
    _summarize_trigger_sources(df_signals)

    print("\n=== Cooldown Sanity Check ===")
    entries = _parse_event_log()
    _check_cooldowns(entries)

    print("\n=== Event Log Tail ===")
    _print_recent_events(entries)


if __name__ == "__main__":
    main()
