.mode list
.separator |
.print Latest Signal Time:
SELECT MAX(timestamp) FROM signals;
.print Total Signals in DB:
SELECT COUNT(*) FROM signals;
.print Signals After Restart (11:57:19):
SELECT COUNT(*) FROM signals WHERE timestamp >= '2026-02-18 11:57:19';
.print Sample Recent Signals:
SELECT timestamp, signal_type FROM signals ORDER BY timestamp DESC LIMIT 5;
