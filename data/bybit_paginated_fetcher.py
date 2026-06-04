"""
Bybit Paginated OHLCV Fetcher
==============================
Fetches multi-page historical kline data from Bybit Linear Futures API.
Paginates backward using the `end` parameter.
Used for initial backfill of 5m data for Flow Engine eligible symbols.

Bybit klines format (returned newest-first):
[timestamp_ms, open, high, low, close, volume, turnover]
"""

import asyncio
import logging
import sqlite3
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import aiohttp

from core.config import Config
from core.database import DatabaseManager

logger = logging.getLogger(__name__)

BYBIT_BASE_URL = "https://api.bybit.com"
BYBIT_KLINES_ENDPOINT = "/v5/market/kline"

# Internal interval map — 5m only; no dependency on bybit_futures_fetcher
PAGINATED_INTERVAL_MAP = {
    "5m": "5",
}

REQUEST_DELAY_SECONDS = 0.15
INTER_SYMBOL_DELAY_SECONDS = 1.5
MAX_PAGES = 9
BARS_PER_PAGE = 1000


class BybitPaginatedFetcher:
    """
    Async context manager for paginated Bybit USDM Futures OHLCV backfill.

    Paginates backward using the `end` parameter to fetch extended history.
    Writes to ohlcv_data with source='bybit_paginated'.

    Usage:
        async with BybitPaginatedFetcher() as fetcher:
            count = await fetcher.fetch_and_save("BTCUSDT", "5m", pages=9)
            results = await fetcher.backfill_symbols(symbols, "5m", pages=9)
    """

    def __init__(self):
        self.db = DatabaseManager()
        self.session: Optional[aiohttp.ClientSession] = None
        self._last_request_time = 0.0

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"Content-Type": "application/json"},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _rate_limit(self):
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < REQUEST_DELAY_SECONDS:
            await asyncio.sleep(REQUEST_DELAY_SECONDS - elapsed)
        self._last_request_time = time.monotonic()

    async def _fetch_page(
        self,
        symbol: str,
        bybit_interval: str,
        end_ms: Optional[int] = None,
    ) -> Optional[list]:
        """Fetch one page of klines. Returns raw candle list or None."""
        params = {
            "category": "linear",
            "symbol": symbol,
            "interval": bybit_interval,
            "limit": BARS_PER_PAGE,
        }
        if end_ms is not None:
            params["end"] = end_ms

        try:
            await self._rate_limit()
            async with self.session.get(
                f"{BYBIT_BASE_URL}{BYBIT_KLINES_ENDPOINT}",
                params=params,
            ) as resp:
                if resp.status != 200:
                    logger.error(
                        f"[PAGINATED] HTTP {resp.status} for {symbol}"
                    )
                    return None

                data = await resp.json()

                if data.get("retCode") != 0:
                    logger.error(
                        f"[PAGINATED] API error for {symbol}: "
                        f"{data.get('retMsg')}"
                    )
                    return None

                candles = data.get("result", {}).get("list", [])
                return candles if candles else None

        except asyncio.TimeoutError:
            logger.error(f"[PAGINATED] Timeout for {symbol}")
            return None
        except Exception as e:
            logger.error(f"[PAGINATED] Exception for {symbol}: {e}")
            return None

    async def fetch_and_save(
        self,
        symbol: str,
        interval: str = "5m",
        pages: int = MAX_PAGES,
    ) -> int:
        """
        Fetch `pages` pages of history for symbol and save to ohlcv_data.
        Paginates backward using end= on each successive call.
        Returns total rows written (INSERT OR IGNORE — duplicates skipped).
        """
        bybit_interval = PAGINATED_INTERVAL_MAP.get(interval)
        if not bybit_interval:
            logger.error(f"[PAGINATED] Unsupported interval: {interval}")
            return 0

        all_candles: list = []
        end_ms: Optional[int] = None

        for page in range(pages):
            candles = await self._fetch_page(symbol, bybit_interval, end_ms)

            if not candles:
                logger.warning(
                    f"[PAGINATED] {symbol} page {page + 1}: no data — stopping"
                )
                break

            all_candles.extend(candles)
            oldest_ts_ms = int(candles[-1][0])
            end_ms = oldest_ts_ms - 1

            logger.debug(
                f"[PAGINATED] {symbol} page {page + 1}/{pages}: "
                f"{len(candles)} candles, oldest={oldest_ts_ms}"
            )

        if not all_candles:
            logger.warning(f"[PAGINATED] {symbol}: no data fetched")
            return 0

        written = self._save_to_db(all_candles, symbol, interval)
        return written

    async def backfill_symbols(
        self,
        symbols: List[str],
        interval: str = "5m",
        pages: int = MAX_PAGES,
    ) -> Dict[str, int]:
        """
        Backfill multiple symbols sequentially with inter-symbol delay.
        Returns dict: symbol -> rows_written.
        """
        results: Dict[str, int] = {}
        total = len(symbols)

        for idx, symbol in enumerate(symbols):
            logger.info(f"[PAGINATED] Backfilling {symbol} ({idx + 1}/{total})")
            written = await self.fetch_and_save(symbol, interval, pages)
            results[symbol] = written
            logger.info(f"[PAGINATED] {symbol}: {written} rows written")

            if idx < total - 1:
                await asyncio.sleep(INTER_SYMBOL_DELAY_SECONDS)

        total_written = sum(results.values())
        logger.info(
            f"[PAGINATED] Backfill complete: "
            f"{len(results)} symbols, {total_written} total rows"
        )
        return results

    def _save_to_db(self, candles: list, symbol: str, interval: str) -> int:
        """
        Persist raw Bybit candle list to ohlcv_data.
        Bybit format (newest-first): [ts_ms, open, high, low, close, vol, turnover]
        Volume cast to int — matches ohlcv_data column type (INTEGER DEFAULT 0).
        """
        written = 0
        try:
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()

            for c in candles:
                try:
                    ts_ms = int(c[0])
                    ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
                    timestamp = ts.strftime("%Y-%m-%d %H:%M:%S")

                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO ohlcv_data
                            (symbol, timeframe, timestamp,
                             open, high, low, close, volume, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            symbol,
                            interval,
                            timestamp,
                            float(c[1]),
                            float(c[2]),
                            float(c[3]),
                            float(c[4]),
                            int(float(c[5])),
                            "bybit_paginated",
                        ),
                    )
                    written += cursor.rowcount

                except (IndexError, ValueError, TypeError) as e:
                    logger.warning(
                        f"[PAGINATED] Skipping malformed candle "
                        f"for {symbol}: {c} — {e}"
                    )
                    continue

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"[PAGINATED] DB save error for {symbol}: {e}")

        return written
