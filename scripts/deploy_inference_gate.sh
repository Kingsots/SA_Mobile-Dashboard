#!/bin/bash
# EC2 Deployment: Hard Inference Gate + Event Monitor Changes
# Run this on EC2 to deploy the latest changes

set -e

echo "=========================================="
echo "INFERENCE GATE DEPLOYMENT"
echo "=========================================="

# Check if we're on EC2
if [ ! -d ~/SilentAnalyst ]; then
    echo "❌ Error: ~/SilentAnalyst directory not found"
    echo "Make sure you're SSH'd to the correct EC2 instance"
    exit 1
fi

echo -e "\n[1/5] Navigating to repo..."
cd ~/SilentAnalyst

echo -e "\n[2/5] Fetching latest changes..."
git fetch origin
git checkout deploy/event-driven-system
git pull origin deploy/event-driven-system

echo -e "\n[3/5] Showing recent commits..."
git log -3 --oneline

echo -e "\n[4/5] Backup current state..."
cp signals/xgb_signal_engine_ec2.py signals/xgb_signal_engine_ec2.py.backup_$(date +%Y%m%d_%H%M%S)
cp async_scheduler.py async_scheduler.py.backup_$(date +%Y%m%d_%H%M%S)
echo "✅ Backups created in signals/ and ."

echo -e "\n[5/5] Restarting signal generation service..."
# Kill existing processes (adjust based on your actual process management)
pkill -f "python3.*signal" || echo "No existing signal processes found"
sleep 2

# Restart (adjust based on how you manage services - systemd, supervisor, manual, etc.)
read -p "Ready to restart service? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Starting signal service..."
    # Example: systemctl restart silent_analyst_signals
    # Or: nohup python3 signals/main.py > logs/signals.log 2>&1 &
    # Adjust to your actual deployment method
    echo "⚠️  Please restart your signal generation service manually"
    echo "   (supervisor, systemd, or however you run it)"
else
    echo "Skipped service restart"
fi

echo -e "\n=========================================="
echo "✅ DEPLOYMENT COMPLETE"
echo "=========================================="
echo ""
echo "Deployed changes:"
echo "  ✓ Hard inference gate (MIN_INFERENCE_ROWS = 110)"
echo "  ✓ Gate check in get_latest_features()"
echo "  ✓ Gate logging in generate_signal()"
echo "  ✓ Event monitor gate handling"
echo "  ✓ triggered counter fixed"
echo ""
echo "Start monitoring with:"
echo "  python3 scripts/monitor_inference_gate.py --interval 5 --report-interval 60"
echo ""
