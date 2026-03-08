#!/usr/bin/env python3
"""Trigger model training remotely via SSH"""
import subprocess
import sys

key_file = r"C:\Users\bigso\Downloads\opticore-key.pem"
host = "ubuntu@52.90.60.32"

# Python code to run on remote server
python_code = """
import sys; sys.path.insert(0, '/home/ubuntu/opticore-bot')
import asyncio
from async_scheduler import MLPipelineScheduler

async def train():
    scheduler = MLPipelineScheduler()
    await scheduler.eod_pipeline_job()

asyncio.run(train())
"""

# Escape for shell
cmd = [
    "ssh",
    "-i", key_file,
    host,
    f"cd /home/ubuntu/opticore-bot && python3 -c \"{python_code}\""
]

print("🚀 Triggering remote training...")
result = subprocess.run(cmd, capture_output=True, text=True)

if result.returncode == 0:
    print("✅ Training triggered successfully")
    print(result.stdout)
else:
    print("❌ Training failed")
    print(result.stderr)
    sys.exit(1)
