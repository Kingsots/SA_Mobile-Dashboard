#!/bin/bash
# EC2 Deployment Script for Event-Driven System
# Run this on EC2 after SSH connection

set -e  # Exit on any error

echo "=========================================="
echo "EC2 DEPLOYMENT: Event-Driven System"
echo "=========================================="

# Step 1: Navigate and fetch
echo -e "\n[1/8] Fetching deployment branch..."
cd ~/opticore-bot
git fetch origin
git checkout deploy/event-driven-system
git pull origin deploy/event-driven-system
git log -3 --oneline

# Step 2: Backup database
echo -e "\n[2/8] Backing up database..."
cp data/trading_bot.db data/trading_bot.db.bak_$(date +%Y%m%d_%H%M)
ls -lh data/trading_bot.db*

# Step 3: Activate venv and run migration
echo -e "\n[3/8] Running database migration..."
source .venv/bin/activate
python scripts/migrate_add_triggered_by.py

# Step 4: Verify schema
echo -e "\n[4/8] Verifying triggered_by column..."
sqlite3 data/trading_bot.db "PRAGMA table_info(ml_signals);" | grep triggered_by

# Step 5: Run validation
echo -e "\n[5/8] Running validation tests..."
python scripts/validate_event_system.py
pytest tests/test_events_basic.py -v

# Step 6: Add config (event monitoring disabled)
echo -e "\n[6/8] Adding configuration (USE_EVENT_MONITOR=false)..."
if ! grep -q "USE_EVENT_MONITOR" .env; then
    cat >> .env <<'EOF'

# Event-Driven System (DISABLED for initial deploy)
USE_EVENT_MONITOR=false
EVENT_MONITOR_CHECK_FREQ_SECONDS=300
MIN_CONFIDENCE_ML=0.65
REQUIRED_RULE_MATCHES=2
EVENT_COOLDOWN_SECONDS=3600
COOLDOWN_HOURS_SAME_TRADE=4
PORTFOLIO_MAX_ACTIVE=4
EOF
    echo "✅ Configuration added"
else
    echo "⚠️  Configuration already exists"
fi
grep -A8 "USE_EVENT_MONITOR" .env

# Step 7: Merge to main
echo -e "\n[7/8] Merging to main branch..."
git checkout main
git merge --no-ff deploy/event-driven-system -m "Merge event-driven system deployment"
git push origin main

# Step 8: Restart scheduler
echo -e "\n[8/8] Restarting trading scheduler..."
sudo systemctl restart trading-scheduler
sleep 3
journalctl -u trading-scheduler -n 50 --no-pager

echo -e "\n=========================================="
echo "✅ DEPLOYMENT COMPLETE"
echo "=========================================="
echo "Monitor logs: tail -f ~/opticore-bot/logs/scheduler.log"
echo "Check status: systemctl status trading-scheduler"
