@echo off
echo ==========================================
echo   Starting Trading Bot (Weekly Refresh)
echo ==========================================

REM --- Set working directory ---
cd /d "C:\Users\bigso\Downloads\ML"

REM --- Get current day of week (0=Sunday, 1=Monday, ..., 6=Saturday) ---
for /f "tokens=1 delims=." %%a in ('wmic path Win32_LocalTime get DayOfWeek ^| findstr [0-6]') do set dow=%%a

REM --- Once a week retraining (Monday only) ---
if "%dow%"=="1" (
    echo Today is Monday - Running Backfill + Training
    "venv\Scripts\python.exe" main.py backfill
    "venv\Scripts\python.exe" train_model.py
) else (
    echo Today is not Monday - Skipping backfill/training
)

REM --- Start continuous monitoring ---
echo Starting Scheduler...
"venv\Scripts\python.exe" robust_scheduler.py

pause
