#!/usr/bin/env python3
"""
Manual 4h data fetch script - pulls fresh market data immediately
Usage: python3 fetch_fresh_4h_data.py
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def main():
    from data.tiingo_fetcher import TiingoFetcher
    import logging
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    print("=" * 80)
    print("🔄 MANUAL FRESH DATA FETCH - 4h OHLCV")
    print("=" * 80)
    
    try:
        async with TiingoFetcher() as fetcher:
            # Check rate limits first
            stats = fetcher.rate_limiter.get_usage_stats()
            print(f"\n📊 API Rate Limit Status:")
            print(f"   Hourly: {stats.get('hourly_remaining', '?')}/{stats.get('hourly_limit', '?')} remaining")
            print(f"   Daily: {stats.get('daily_remaining', '?')}/{stats.get('daily_limit', '?')} remaining")
            
            if stats.get('hourly_remaining', 0) < 5 or stats.get('daily_remaining', 0) < 10:
                print(f"\n❌ Rate limit low - aborting fetch")
                return 1
            
            # Fetch fresh 4h data
            print(f"\n📊 Fetching fresh 4h data for all symbols...")
            results = await fetcher.fetch_batch('4h', None)
            print(f"✅ Fresh 4h data fetch completed!")
            print(f"   Retrieved fresh candles for {len(results)} symbols")
        
    except Exception as e:
        print(f"❌ Fetch failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("\n" + "=" * 80)
    print("✅ SUCCESS - Fresh 4h data ready for event monitor")
    print("=" * 80)
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
