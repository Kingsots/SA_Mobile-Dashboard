#!/usr/bin/env python3
"""
Generate 30-Minute Data for Watchlist
Fetches actual 30m OHLCV data from Yahoo Finance for all symbols in watchlist.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.config import Config
from data.generator import DataGenerator
from utils.logger import setup_logger

logger = setup_logger('Generate30mData')


def main():
    """Generate 30-minute data for all watchlist symbols"""
    
    print("=" * 60)
    print("30-Minute Data Generator")
    print("=" * 60)
    print()
    
    # Display configuration
    watchlist = Config.get_symbol_list()
    print(f"Watchlist: {len(watchlist)} symbols")
    print(f"Symbols: {', '.join(watchlist)}")
    print(f"Data Directory: {Config.DATA_DIR}")
    print()
    
    # Confirm
    response = input("Generate 30m data for all symbols? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        return
    
    print()
    print("Starting data generation...")
    print()
    
    # Generate data
    success_count, fail_count = DataGenerator.generate_all_30m_data(
        watchlist=watchlist,
        save_csv=True
    )
    
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"✅ Successfully generated: {success_count}/{len(watchlist)}")
    print(f"❌ Failed: {fail_count}/{len(watchlist)}")
    print()
    
    if fail_count > 0:
        print("⚠️  Some symbols failed. They may not be available on Yahoo Finance.")
        print("   Check the logs for details.")
    
    print()
    print("30m CSV files saved to:", Config.DATA_DIR)
    print()


if __name__ == "__main__":
    main()
