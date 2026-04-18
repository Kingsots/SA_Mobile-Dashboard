#!/usr/bin/env python3
"""
Daily OHLCV Backfill Script for OptiCore SA
Backfills daily (1d) data from Tiingo API into trading_bot.db
Target: 100+ clean trading days for all pairs
Start: 2025-09-01, End: today
"""

import sys
import os
import requests
import time
import logging
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import DatabaseManager

# Configuration
TIINGO_TOKEN = "721e7de39daa4eaf3f119bbbee55ba64a8d700eb"
TIINGO_API_URL = "https://api.tiingo.com/tiingo/fx/{ticker}/prices"
TIINGO_COMMODITY_URL = "https://api.tiingo.com/tiingo/daily/{ticker}/prices"

START_DATE = "2025-09-01"
END_DATE = datetime.now().strftime("%Y-%m-%d")

PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "AUDJPY",
    "CADJPY", "EURJPY", "EURGBP", "GBPJPY", "XAUUSD", "AUDCAD"
]

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('/home/ubuntu/SilentAnalyst/backfill_daily_ohlcv.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DailyOHLCVBackfiller:
    def __init__(self, db_path="/home/ubuntu/SilentAnalyst/trading_bot.db"):
        """Initialize backfiller with database connection."""
        self.db = DatabaseManager(db_path)
        self.stats = {}
        
    def fetch_daily_data(self, ticker):
        """Fetch daily OHLCV data from Tiingo API."""
        try:
            # Determine if it's a commodity or forex pair
            if ticker == "XAUUSD":
                url = TIINGO_COMMODITY_URL.format(ticker="XAUUSD")
            else:
                # Forex tickers are lowercase without slash
                ticker_lower = ticker.lower()
                url = TIINGO_API_URL.format(ticker=ticker_lower)
            
            params = {
                "startDate": START_DATE,
                "endDate": END_DATE,
                "resampleFreq": "1day",
                "token": TIINGO_TOKEN
            }
            
            logger.info(f"[FETCH] {ticker}: GET {url}")
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"[FETCH] {ticker}: HTTP {response.status_code} - {response.text}")
                return []
            
            data = response.json()
            
            if not data or len(data) == 0:
                logger.warning(f"[FETCH] {ticker}: No data returned from API")
                return []
            
            logger.info(f"[FETCH] {ticker}: Got {len(data)} bars")
            return data
            
        except requests.RequestException as e:
            logger.error(f"[FETCH] {ticker}: Request error - {e}")
            return []
        except Exception as e:
            logger.error(f"[FETCH] {ticker}: Unexpected error - {e}")
            return []
    
    def insert_daily_data(self, ticker, bars):
        """Insert daily bars into ohlcv_data table using correct column names."""
        if not bars:
            self.stats[ticker] = {"fetched": 0, "inserted": 0, "skipped": 0}
            return
        
        inserted = 0
        skipped = 0
        
        for bar in bars:
            try:
                # Parse Tiingo response
                timestamp = bar.get('date')
                open_price = bar.get('open')
                high_price = bar.get('high')
                low_price = bar.get('low')
                close_price = bar.get('close')
                volume = bar.get('volume', 0)
                
                if not all([timestamp, open_price, close_price]):
                    logger.warning(f"[INSERT] {ticker}: Incomplete bar data - skipping")
                    skipped += 1
                    continue
                
                # Insert using INSERT OR IGNORE (safe re-run)
                # Note: Column names are 'symbol' and 'timeframe' (not 'ticker' and 'interval')
                query = """
                INSERT OR IGNORE INTO ohlcv_data 
                (symbol, timeframe, timestamp, open, high, low, close, volume, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                
                self.db.conn.execute(query, (
                    ticker, 'daily', timestamp,
                    open_price, high_price, low_price, close_price, volume, 'tiingo_backfill'
                ))
                inserted += 1
                
            except Exception as e:
                logger.error(f"[INSERT] {ticker}: Error inserting bar - {e}")
                skipped += 1
        
        self.db.conn.commit()
        
        self.stats[ticker] = {
            "fetched": len(bars),
            "inserted": inserted,
            "skipped": skipped
        }
        
        logger.info(f"[INSERT] {ticker}: inserted={inserted}, skipped={skipped}")
    
    def backfill_all_pairs(self):
        """Backfill all trading pairs."""
        logger.info(f"[START] Backfilling daily OHLCV from {START_DATE} to {END_DATE}")
        logger.info(f"[START] Pairs: {', '.join(PAIRS)}")
        
        for ticker in PAIRS:
            logger.info(f"\n========== {ticker} ==========")
            
            # Fetch data
            bars = self.fetch_daily_data(ticker)
            
            # Insert data
            self.insert_daily_data(ticker, bars)
            
            # Respect API rate limits
            time.sleep(0.5)
        
        logger.info("\n========== BACKFILL COMPLETE ==========")
    
    def verify_backfill(self):
        """Verify bar counts per symbol (corrected column names)."""
        logger.info("\n========== VERIFICATION ==========")
        
        try:
            query = """
            SELECT symbol, COUNT(*) as bar_count, 
                   MIN(timestamp) as earliest, MAX(timestamp) as latest
            FROM ohlcv_data
            WHERE timeframe = 'daily' AND symbol IN ({})
            GROUP BY symbol
            ORDER BY symbol
            """.format(','.join(['?' for _ in PAIRS]))
            
            cursor = self.db.conn.execute(query, PAIRS)
            results = cursor.fetchall()
            
            logger.info("\nFinal Bar Counts (Daily Timeframe):")
            logger.info("-" * 70)
            
            all_sufficient = True
            for row in results:
                symbol, bar_count, earliest, latest = row
                status = "✓ OK" if bar_count >= 140 else "✗ INSUFFICIENT"
                logger.info(f"{symbol:10} | {bar_count:3} bars | {earliest} to {latest} | {status}")
                
                if bar_count < 140:
                    all_sufficient = False
            
            logger.info("-" * 70)
            
            # Check for missing pairs
            backfilled_symbols = [row[0] for row in results]
            missing = set(PAIRS) - set(backfilled_symbols)
            
            if missing:
                logger.warning(f"\nMissing pairs (no data): {', '.join(missing)}")
                all_sufficient = False
            
            logger.info(f"\nOverall Status: {'✓ ALL PAIRS SUFFICIENT' if all_sufficient else '✗ SOME PAIRS MISSING DATA'}")
            
            return all_sufficient
            
        except Exception as e:
            logger.error(f"[VERIFY] Error - {e}")
            return False
    
    def print_stats_summary(self):
        """Print summary statistics."""
        logger.info("\n========== BACKFILL STATISTICS ==========")
        
        total_fetched = sum(s['fetched'] for s in self.stats.values())
        total_inserted = sum(s['inserted'] for s in self.stats.values())
        total_skipped = sum(s['skipped'] for s in self.stats.values())
        
        logger.info(f"Total fetched:  {total_fetched} bars")
        logger.info(f"Total inserted: {total_inserted} bars")
        logger.info(f"Total skipped:  {total_skipped} bars")
        logger.info("\nPer-ticker breakdown:")
        
        for ticker in PAIRS:
            if ticker in self.stats:
                s = self.stats[ticker]
                logger.info(f"  {ticker:10} | fetch={s['fetched']:3} | insert={s['inserted']:3} | skip={s['skipped']:3}")


def main():
    """Main execution."""
    logger.info("=" * 70)
    logger.info("DAILY OHLCV BACKFILL - OptiCore SA")
    logger.info("=" * 70)
    
    backfiller = DailyOHLCVBackfiller()
    
    try:
        # Backfill all pairs
        backfiller.backfill_all_pairs()
        
        # Print statistics
        backfiller.print_stats_summary()
        
        # Verify backfill
        success = backfiller.verify_backfill()
        
        logger.info("\n" + "=" * 70)
        if success:
            logger.info("✓ BACKFILL SUCCESSFUL - All pairs have 140+ bars")
        else:
            logger.warning("⚠ BACKFILL INCOMPLETE - Some pairs missing data")
        logger.info("=" * 70)
        
        return 0 if success else 1
        
    except Exception as e:
        logger.error(f"[MAIN] Fatal error - {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
