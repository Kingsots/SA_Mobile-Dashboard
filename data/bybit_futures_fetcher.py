"""
Bybit USDM Futures OHLCV Fetcher
=================================
Fetches kline data from Bybit Linear Futures API.
Mirrors TiingoFetcher interface for drop-in compatibility.
Writes to ohlcv_data table with source='bybit_futures'.

Bybit klines format (returned newest-first):
[timestamp_ms, open, high, low, close, volume, turnover]
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import sqlite3
import aiohttp
import pandas as pd

from core.config import Config
from core.database import DatabaseManager

logger = logging.getLogger(__name__)

# Bybit interval mapping: SA interval -> Bybit API param
BYBIT_INTERVAL_MAP = {
    "5m":   "5",
    "15m":  "15",
    "30m":  "30",
    "1h":   "60",
    "2h":   "120",
    "4h":   "240",
    "1d":   "D",
    "D":    "D",
}

BYBIT_BASE_URL = "https://api.bybit.com"
BYBIT_KLINES_ENDPOINT = "/v5/market/kline"
BYBIT_TICKERS_ENDPOINT = "/v5/market/tickers"

# Rate limiting: Bybit allows 120 requests/min on public endpoints
REQUEST_DELAY_SECONDS = 0.15  # ~6-7 req/sec, well within limits


class BybitFuturesFetcher:
    """
    Async context manager for fetching Bybit USDM Futures OHLCV data.

    Usage:
        async with BybitFuturesFetcher() as fetcher:
            df = await fetcher.fetch_price("BTCUSDT", "1h")
            batch = await fetcher.fetch_batch("1h", ["BTCUSDT", "ETHUSDT"])
    """

    def __init__(self):
        self.db = DatabaseManager()
        self.session: Optional[aiohttp.ClientSession] = None
        self._request_count = 0
        self._last_request_time = 0.0

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"Content-Type": "application/json"}
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _rate_limit(self):
        """Simple rate limiter to stay within Bybit limits."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < REQUEST_DELAY_SECONDS:
            await asyncio.sleep(REQUEST_DELAY_SECONDS - elapsed)
        self._last_request_time = time.monotonic()
        self._request_count += 1

    async def fetch_price(
        self,
        symbol: str,
        interval: str,
        limit: int = 200
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV klines for a single symbol.

        Args:
            symbol:   Bybit symbol e.g. 'BTCUSDT'
            interval: SA-style interval e.g. '1h', '4h', 'D'
            limit:    Number of bars to fetch (max 1000)

        Returns:
            DataFrame with columns [timestamp, open, high, low, close, volume]
            or None on error.
        """
        bybit_interval = BYBIT_INTERVAL_MAP.get(interval)
        if not bybit_interval:
            logger.error(f"[BYBIT] Unsupported interval: {interval}")
            return None

        params = {
            "category": "linear",
            "symbol": symbol,
            "interval": bybit_interval,
            "limit": min(limit, 1000),
        }

        try:
            await self._rate_limit()
            async with self.session.get(
                f"{BYBIT_BASE_URL}{BYBIT_KLINES_ENDPOINT}",
                params=params
            ) as resp:
                if resp.status != 200:
                    logger.error(f"[BYBIT] HTTP {resp.status} for {symbol} {interval}")
                    return None

                data = await resp.json()

                if data.get("retCode") != 0:
                    logger.error(
                        f"[BYBIT] API error for {symbol} {interval}: "
                        f"{data.get('retMsg')}"
                    )
                    return None

                candles = data.get("result", {}).get("list", [])
                if not candles:
                    logger.warning(f"[BYBIT] No candles returned for {symbol} {interval}")
                    return None

                return self._normalize_ohlcv(candles, symbol, interval)

        except asyncio.TimeoutError:
            logger.error(f"[BYBIT] Timeout fetching {symbol} {interval}")
            return None
        except Exception as e:
            logger.error(f"[BYBIT] Exception fetching {symbol} {interval}: {e}")
            return None

    async def fetch_batch(
        self,
        interval: str,
        symbols: List[str],
        limit: int = 200,
        save_to_db: bool = True
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch OHLCV for multiple symbols sequentially.

        Args:
            interval:    SA-style interval
            symbols:     List of Bybit symbols
            limit:       Bars per symbol
            save_to_db:  Whether to persist to ohlcv_data table

        Returns:
            Dict mapping symbol -> DataFrame
        """
        results = {}
        for symbol in symbols:
            df = await self.fetch_price(symbol, interval, limit)
            if df is not None:
                results[symbol] = df
                if save_to_db:
                    self._save_to_db(df, symbol, interval)
            else:
                logger.warning(f"[BYBIT] Skipping {symbol} {interval} — no data")

        logger.info(
            f"[BYBIT] Batch complete: {len(results)}/{len(symbols)} symbols "
            f"fetched for {interval}"
        )
        return results

    async def fetch_all_tickers(self) -> Optional[pd.DataFrame]:
        """
        Fetch 24h ticker data for ALL Bybit USDT linear perpetuals.
        Used by DailyScanner for filter calculations.

        Returns:
            DataFrame with all ticker fields or None on error.
        """
        params = {"category": "linear"}

        try:
            await self._rate_limit()
            async with self.session.get(
                f"{BYBIT_BASE_URL}{BYBIT_TICKERS_ENDPOINT}",
                params=params
            ) as resp:
                if resp.status != 200:
                    logger.error(f"[BYBIT] HTTP {resp.status} fetching tickers")
                    return None

                data = await resp.json()
                if data.get("retCode") != 0:
                    logger.error(f"[BYBIT] Ticker API error: {data.get('retMsg')}")
                    return None

                items = data.get("result", {}).get("list", [])
                if not items:
                    return None

                # Filter USDT perpetuals only
                usdt = [i for i in items if i.get("symbol", "").endswith("USDT")]

                df = pd.DataFrame(usdt)

                # Cast numeric fields
                numeric_fields = [
                    "lastPrice", "prevPrice24h", "price24hPcnt",
                    "highPrice24h", "lowPrice24h", "volume24h",
                    "turnover24h", "openInterest", "openInterestValue",
                    "fundingRate"
                ]
                for field in numeric_fields:
                    if field in df.columns:
                        df[field] = pd.to_numeric(df[field], errors="coerce")

                logger.info(f"[BYBIT] Fetched {len(df)} USDT perpetual tickers")
                return df

        except Exception as e:
            logger.error(f"[BYBIT] Exception fetching tickers: {e}")
            return None

    def _normalize_ohlcv(
        self,
        candles: list,
        symbol: str,
        interval: str
    ) -> pd.DataFrame:
        """
        Normalize Bybit klines response to standard OHLCV DataFrame.

        Bybit format (newest first):
        [timestamp_ms, open, high, low, close, volume, turnover]
        """
        rows = []
        for c in candles:
            try:
                ts_ms = int(c[0])
                ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
                rows.append({
                    "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                    "open":      float(c[1]),
                    "high":      float(c[2]),
                    "low":       float(c[3]),
                    "close":     float(c[4]),
                    "volume":    float(c[5]),
                    "turnover":  float(c[6]),
                    "symbol":    symbol,
                    "timeframe": interval,
                    "source":    "bybit_futures",
                })
            except (IndexError, ValueError, TypeError) as e:
                logger.warning(f"[BYBIT] Skipping malformed candle: {c} — {e}")
                continue

        if not rows:
            return None

        df = pd.DataFrame(rows)
        # Bybit returns newest first — reverse to chronological order
        df = df.iloc[::-1].reset_index(drop=True)
        return df

    def _save_to_db(self, df: pd.DataFrame, symbol: str, interval: str):
        """
        Persist OHLCV DataFrame to ohlcv_data table.
        Uses INSERT OR IGNORE to avoid duplicates.
        """
        try:
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()

            for _, row in df.iterrows():
                cursor.execute("""
                    INSERT OR IGNORE INTO ohlcv_data
                    (symbol, timeframe, timestamp, open, high, low, close, volume, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol,
                    interval,
                    row["timestamp"],
                    row["open"],
                    row["high"],
                    row["low"],
                    row["close"],
                    int(row["volume"]),
                    "bybit_futures",
                ))

            conn.commit()
            logger.debug(
                f"[BYBIT] Saved {len(df)} candles to DB: {symbol} {interval}"
            )

        except Exception as e:
            logger.error(f"[BYBIT] DB save error for {symbol} {interval}: {e}")
