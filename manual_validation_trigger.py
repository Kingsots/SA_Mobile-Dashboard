#!/usr/bin/env python3
"""
Manual trigger for time-based validation job
Used to accelerate Phase 2 sample collection for testing
"""
import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from async_scheduler import MLPipelineScheduler

async def main():
    scheduler = MLPipelineScheduler(enable_telegram=False)
    
    print("[Manual Trigger] Starting validation mode sampling...")
    print()
    
    # Run the validation job for both intervals
    for interval in ['30m', '1h', '4h']:
        print(f"Running validation for {interval}...")
        try:
            await scheduler.time_based_fallback_job(interval=interval)
        except Exception as e:
            print(f"Error in {interval}: {e}")
        print()
    
    print("[Manual Trigger] Validation sampling complete")
    print("Check: /home/ubuntu/SilentAnalyst/logs/phase2_comparison.log")

if __name__ == '__main__':
    asyncio.run(main())
