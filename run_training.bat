@echo off
setlocal enabledelayedexpansion
set KEY=C:\Users\bigso\Downloads\opticore-key.pem
set HOST=ubuntu@52.90.60.32

echo Checking current models...
ssh -i "%KEY%" "%HOST%" "ls -lh /home/ubuntu/opticore-bot/data/models/*.pkl | tail -5"

echo.
echo Triggering training...
ssh -i "%KEY%" "%HOST%" "cd /home/ubuntu/opticore-bot && python3 -c 'import sys, asyncio; sys.path.insert(0, \"/home/ubuntu/opticore-bot\"); exec(open(\"trigger_training.py\").read())'"
