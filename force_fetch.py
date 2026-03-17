#!/usr/bin/env python3
"""
Force immediate fetch of Tiingo data
"""
import asyncio
import sys
from data.tiingo_fetcher import TiingoFetcher
from core.config import Config
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def force_fetch():
    """Execute immediate data fetch"""
    try:
        logger.info("=" * 70)
        logger.info("🔄 FORCE FETCH: Starting immediate data fetch")
        logger.info("=" * 70)
        
        async with TiingoFetcher() as fetcher:
            symbols = Config.get_symbol_list()
            logger.info(f"Fetching {len(symbols)} symbols: {symbols}")
            
            results = await fetcher.fetch_batch('30m', symbols)
            
            logger.info("=" * 70)
            logger.info(f"✅ FETCH COMPLETE: {len(results)} symbols successfully fetched")
            logger.info("=" * 70)
            
            # Show stats
            stats = fetcher.rate_limiter.get_usage_stats()
            logger.info(f"📊 Rate Limits:")
            logger.info(f"   Hourly: {stats['hourly_used']}/{stats['hourly_limit']} used ({stats['hourly_remaining']} remaining)")
            logger.info(f"   Daily: {stats['daily_used']}/{stats['daily_limit']} used ({stats['daily_remaining']} remaining)")
            
            return True
    
    except Exception as e:
        logger.error("=" * 70)
        logger.error(f"❌ FETCH FAILED: {e}")
        logger.error("=" * 70)
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = asyncio.run(force_fetch())
    sys.exit(0 if success else 1)
