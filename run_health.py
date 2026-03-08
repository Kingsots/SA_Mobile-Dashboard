import asyncio
import logging
from async_scheduler import MLPipelineScheduler

logging.basicConfig(level=logging.INFO)

async def main():
    # Initialize scheduler with telegram enabled flag
    sched = MLPipelineScheduler(enable_telegram=True)
    # Run health check once
    try:
        await sched.health_check_job()
    except Exception as e:
        logging.error("Health check run failed: %s", e)

if __name__ == '__main__':
    asyncio.run(main())
