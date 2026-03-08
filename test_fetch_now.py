"""Quick test of Tiingo fetch"""
import asyncio
from data.tiingo_fetcher import TiingoFetcher
from core.config import Config

async def test_fetch():
    fetcher = TiingoFetcher()
    
    # Test with just EURUSD first (forex should work)
    print("\n🧪 Testing EURUSD fetch...")
    results = await fetcher.fetch_batch('30m', ['EURUSD'])
    
    if results:
        for symbol, df in results.items():
            if df is not None and not df.empty:
                print(f"✅ {symbol}: Got {len(df)} rows")
                print(df.head())
            else:
                print(f"❌ {symbol}: Empty or None")
    else:
        print("❌ No results")
    
    await fetcher.close()

if __name__ == "__main__":
    asyncio.run(test_fetch())
