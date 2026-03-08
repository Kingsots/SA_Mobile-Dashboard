#!/usr/bin/env python3
"""Manually trigger EOD pipeline training with fixed entry prices"""
import sys
import asyncio

sys.path.insert(0, '/home/ubuntu/opticore-bot')

from async_scheduler import MLPipelineScheduler

async def trigger_training():
    print("🚀 Triggering EOD pipeline training...")
    scheduler = MLPipelineScheduler()
    await scheduler.eod_pipeline_job()
    print("✅ Training completed")

if __name__ == "__main__":
    asyncio.run(trigger_training())
