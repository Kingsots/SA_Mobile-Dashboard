# Rollback Plan: v1.5 Event-Driven → v1.4 Time-Based

This document captures the steps to revert the OptiCore bot from the v1.5 event-driven deployment back to the stable v1.4 release.

## 1. Pre-Rollback Checklist
- [ ] Confirm that the v1.4 tag (or commit hash) is available locally and on the EC2 instance.
- [ ] Notify stakeholders that the bot will temporarily pause signal generation during rollback.
- [ ] Snapshot the current database (`trading_bot.db`) and logs (`logs/`) for auditing.
- [ ] Capture the current service status: `sudo systemctl status opticore.service`.

## 2. Disable the Running Service
```bash
sudo systemctl stop opticore.service
sudo systemctl disable opticore.service
```

## 3. Restore Code to v1.4
### Option A: Git checkout (preferred)
```bash
cd /home/ubuntu/opticore-bot
sudo -u ubuntu git fetch --tags
sudo -u ubuntu git checkout v1.4
```

### Option B: Tarball/Backup
If a v1.4 tarball was archived during the upgrade:
```bash
cd /home/ubuntu/opticore-bot
sudo -u ubuntu tar -xzf /path/to/opticore_v1.4_backup.tar.gz --strip-components=1
```

## 4. Restore Python Environment (if dependencies changed)
```bash
cd /home/ubuntu/opticore-bot
sudo -u ubuntu python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 5. Remove v1.5 Artifacts
- Delete event log: `rm -f logs/event_debug.log`
- Remove new migration (if unwanted): `rm -f scripts/migrate_add_triggered_by.py`
- Purge `triggered_by` column (optional):
  ```sql
  sqlite3 trading_bot.db "ALTER TABLE ml_signals DROP COLUMN triggered_by;"
  ```
  *Note*: SQLite requires table recreation to drop columns. Ensure you understand the data impact before proceeding. Alternatively, leave the column in place; it is backwards compatible with v1.4.

## 6. Re-enable v1.4 Scheduler
```bash
sudo systemctl enable opticore.service
sudo systemctl start opticore.service
```

## 7. Post-Rollback Validation
1. Tail the scheduler logs:
   ```bash
   tail -f logs/signal_debug.log
   ```
2. Confirm hourly signals resume without event-driven entries.
3. Verify Telegram alerts use the v1.4 formatting (no trigger metadata section).
4. Notify stakeholders that the rollback completed and the system is stable.

## 8. Rollback Abort / Reapply v1.5
If the rollback needs to be aborted, reapply the v1.5 deployment process:
1. Checkout tag `v1.5-event-driven` again or redeploy the backup package.
2. Re-run the migration: `python scripts/migrate_add_triggered_by.py`
3. Restart the service and validate event-triggered logging.

## 9. Incident Tracking
- Update the incident or change ticket with:
  - Start/finish timestamps
  - Reason for rollback
  - Observed impact
  - Follow-up actions

---
Prepared for the PHASE 6 deployment window to ensure a quick recovery path if issues arise post-release.
