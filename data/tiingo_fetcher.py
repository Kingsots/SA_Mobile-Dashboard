"""
Tiingo API Fetcher - Async data retrieval with rate limiting
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import sqlite3
from pathlib import Path

from core.config import Config
from core.database import DatabaseManager


class RateLimiter:
    """Track API usage and enforce rate limits"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.conn = sqlite3.connect(Config.DB_PATH)
    
    def check_rate_limit(self) -> Tuple[bool, str]:
        """
        Check if we can make a request without exceeding limits
        
        Returns:
            (can_proceed, reason)
        """
        cursor = self.conn.cursor()
        now = datetime.utcnow()
        
        # Check hourly limit
        hour_ago = now - timedelta(hours=1)
        cursor.execute("""
            SELECT COUNT(*) FROM api_usage 
            WHERE api_name = 'tiingo' 
            AND timestamp >= ?
            AND success = 1
        """, (hour_ago.isoformat(),))
        
        hourly_count = cursor.fetchone()[0]
        hourly_limit = Config.TIINGO_MAX_HOURLY_REQUESTS - Config.TIINGO_RATE_LIMIT_BUFFER
        
        if hourly_count >= hourly_limit:
            return False, f"Hourly limit reached: {hourly_count}/{hourly_limit}"
        
        # Check daily limit
        day_ago = now - timedelta(days=1)
        cursor.execute("""
            SELECT COUNT(*) FROM api_usage 
            WHERE api_name = 'tiingo' 
            AND timestamp >= ?
            AND success = 1
        """, (day_ago.isoformat(),))
        
        daily_count = cursor.fetchone()[0]
        daily_limit = Config.TIINGO_MAX_DAILY_REQUESTS - Config.TIINGO_RATE_LIMIT_BUFFER
        
        if daily_count >= daily_limit:
            return False, f"Daily limit reached: {daily_count}/{daily_limit}"
        
        return True, "OK"
    
    def log_request(self, ticker: str, interval: str, success: bool, error_msg: Optional[str] = None):
        """Log API request to database"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO api_usage 
            (timestamp, api_name, endpoint, ticker, interval, success, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.utcnow().isoformat(),
            'tiingo',
            Config.TIINGO_BASE_URL,
            ticker,
            interval,
            1 if success else 0,
            error_msg
        ))
        self.conn.commit()
    
    def get_usage_stats(self) -> Dict:
        """Get current usage statistics"""
        cursor = self.conn.cursor()
        now = datetime.utcnow()
        
        # Hourly stats
        hour_ago = now - timedelta(hours=1)
        cursor.execute("""
            SELECT COUNT(*) FROM api_usage 
            WHERE api_name = 'tiingo' AND timestamp >= ? AND success = 1
        """, (hour_ago.isoformat(),))
        hourly = cursor.fetchone()[0]
        
        # Daily stats
        day_ago = now - timedelta(days=1)
        cursor.execute("""
            SELECT COUNT(*) FROM api_usage 
            WHERE api_name = 'tiingo' AND timestamp >= ? AND success = 1
        """, (day_ago.isoformat(),))
        daily = cursor.fetchone()[0]
        
        return {
            'hourly_used': hourly,
            'hourly_limit': Config.TIINGO_MAX_HOURLY_REQUESTS,
            'hourly_remaining': Config.TIINGO_MAX_HOURLY_REQUESTS - hourly,
            'daily_used': daily,
            'daily_limit': Config.TIINGO_MAX_DAILY_REQUESTS,
            'daily_remaining': Config.TIINGO_MAX_DAILY_REQUESTS - daily
        }
    
    def close(self):
        """Close database connection"""
        self.conn.close()


class TiingoFetcher:
    """Async Tiingo API data fetcher with rate limiting"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.rate_limiter = RateLimiter(self.db)
        self.session: Optional[aiohttp.ClientSession] = None
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Token {Config.TIINGO_API_TOKEN}'
        }
    
    async def _ensure_session(self):
        """Ensure session is initialized"""
        if self.session is None:
            self.session = aiohttp.ClientSession(headers=self.headers)
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
        self.rate_limiter.close()
    
    async def fetch_price(
        self, 
        ticker: str, 
        interval: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV data for a single ticker
        
        Args:
            ticker: Symbol to fetch (e.g., 'EURUSD')
            interval: Timeframe (e.g., '30m', '1h', '1d')
            start_date: Start date for historical data
            end_date: End date for historical data
            
        Returns:
            DataFrame with OHLCV data or None if failed
        """
        # Ensure session is initialized
        await self._ensure_session()
        
        # Check rate limit
        can_proceed, reason = self.rate_limiter.check_rate_limit()
        if not can_proceed:
            print(f"❌ Rate limit exceeded: {reason}")
            return None
        
        # Get Tiingo ticker
        tiingo_ticker = Config.get_tiingo_ticker(ticker)
        
        # Map interval to Tiingo format
        interval_map = {
            '1min': '1Min',
            '5min': '5Min',
            '15min': '15Min',
            '30m': '30Min',      # Support both 30m and 30min
            '30min': '30Min',
            '1h': '1Hour',
            '4h': '4Hour',
            '1d': '1Day'
        }
        tiingo_interval = interval_map.get(interval, interval)
        
        # Build URL
        if interval in ['1d', '1w', '1M']:
            # Use daily endpoint
            url = f"{Config.TIINGO_BASE_URL}/{tiingo_ticker}/prices"
        else:
            # Use intraday endpoint
            url = f"{Config.TIINGO_BASE_URL}/{tiingo_ticker}/prices"
        
        # Build params
        params = {
            'resampleFreq': tiingo_interval
        }
        
        if start_date:
            params['startDate'] = start_date.strftime('%Y-%m-%d')
        else:
            # Default to 90 days ago
            params['startDate'] = (datetime.utcnow() - timedelta(days=90)).strftime('%Y-%m-%d')
        
        if end_date:
            params['endDate'] = end_date.strftime('%Y-%m-%d')
        
        try:
            # Make request
            async with self.session.get(url, params=params, timeout=Config.TIINGO_TIMEOUT) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Normalize to DataFrame
                    if data:
                        df = pd.DataFrame(data)
                        
                        # Rename columns to standard OHLCV
                        df.rename(columns={
                            'date': 'timestamp',
                            'open': 'open',
                            'high': 'high',
                            'low': 'low',
                            'close': 'close',
                            'volume': 'volume'
                        }, inplace=True)
                        
                        # Convert timestamp to datetime
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                        
                        # Add metadata
                        df['ticker'] = ticker
                        df['interval'] = interval
                        df['source'] = 'tiingo'
                        
                        # Save to database
                        self._save_raw_data(df, ticker, interval)
                        
                        # Log success
                        self.rate_limiter.log_request(ticker, interval, True)
                        
                        return df
                    else:
                        error_msg = "Empty response from Tiingo"
                        print(f"⚠️  {ticker} ({interval}): {error_msg}")
                        self.rate_limiter.log_request(ticker, interval, False, error_msg)
                        return None
                else:
                    error_msg = f"HTTP {response.status}: {await response.text()}"
                    print(f"❌ {ticker} ({interval}): {error_msg}")
                    self.rate_limiter.log_request(ticker, interval, False, error_msg)
                    return None
        
        except asyncio.TimeoutError:
            error_msg = "Request timeout"
            print(f"⏰ {ticker} ({interval}): {error_msg}")
            self.rate_limiter.log_request(ticker, interval, False, error_msg)
            return None
        
        except Exception as e:
            error_msg = str(e)
            print(f"💥 {ticker} ({interval}): {error_msg}")
            self.rate_limiter.log_request(ticker, interval, False, error_msg)
            return None
    
    def _save_raw_data(self, df: pd.DataFrame, ticker: str, interval: str):
        """Save raw OHLCV data to database"""
        conn = sqlite3.connect(Config.DB_PATH)
        cursor = conn.cursor()
        
        for _, row in df.iterrows():
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO ohlcv_data 
                    (symbol, timeframe, timestamp, open, high, low, close, volume, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ticker,
                    interval,
                    row['timestamp'].isoformat(),
                    row['open'],
                    row['high'],
                    row['low'],
                    row['close'],
                    row.get('volume', 0),
                    'tiingo'
                ))
            except Exception as e:
                print(f"Error saving row: {e}")
                continue
        
        conn.commit()
        conn.close()
    
    async def fetch_batch(
        self, 
        interval: str,
        symbols: Optional[List[str]] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for multiple symbols with rate limiting
        
        Args:
            interval: Timeframe to fetch
            symbols: List of symbols (default: all watchlist)
            
        Returns:
            Dict mapping symbol -> DataFrame
        """
        if symbols is None:
            symbols = Config.get_symbol_list()
        
        results = {}
        
        print(f"\n{'='*70}")
        print(f"  Fetching {interval} data for {len(symbols)} symbols")
        print(f"{'='*70}\n")
        
        # Get rate limit stats
        stats = self.rate_limiter.get_usage_stats()
        print(f"📊 Rate Limit Status:")
        print(f"   Hourly: {stats['hourly_used']}/{stats['hourly_limit']} ({stats['hourly_remaining']} remaining)")
        print(f"   Daily:  {stats['daily_used']}/{stats['daily_limit']} ({stats['daily_remaining']} remaining)")
        print()
        
        for i, symbol in enumerate(symbols, 1):
            print(f"[{i}/{len(symbols)}] Fetching {symbol}...", end=' ')
            
            df = await self.fetch_price(symbol, interval)
            
            if df is not None:
                results[symbol] = df
                print(f"✅ {len(df)} candles")
            else:
                print(f"❌ Failed")
            
            # Stagger requests
            if i < len(symbols):
                await asyncio.sleep(Config.TIINGO_REQUEST_DELAY)
        
        print(f"\n✅ Fetched data for {len(results)}/{len(symbols)} symbols")
        
        return results
    
    def fallback_to_csv(self, ticker: str, interval: str) -> Optional[pd.DataFrame]:
        """
        Fallback to CSV files if Tiingo fails
        
        Args:
            ticker: Symbol to fetch
            interval: Timeframe
            
        Returns:
            DataFrame from CSV or None
        """
        csv_file = Config.DATA_DIR / f"{ticker}_{interval}.csv"
        
        if csv_file.exists():
            try:
                df = pd.read_csv(csv_file)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df['source'] = 'csv'
                print(f"📂 Loaded {ticker} ({interval}) from CSV: {len(df)} candles")
                return df
            except Exception as e:
                print(f"❌ Error loading CSV: {e}")
                return None
        else:
            print(f"⚠️  CSV not found: {csv_file}")
            return None


async def main():
    """Test Tiingo fetcher"""
    async with TiingoFetcher() as fetcher:
        # Test single symbol
        df = await fetcher.fetch_price('EURUSD', '1h')
        if df is not None:
            print(f"\n✅ Fetched {len(df)} candles for EURUSD")
            print(df.head())
        
        # Test batch fetch
        results = await fetcher.fetch_batch('1h', ['EURUSD', 'GBPUSD', 'USDJPY'])
        print(f"\n✅ Batch fetch complete: {len(results)} symbols")


if __name__ == '__main__':
    asyncio.run(main())
