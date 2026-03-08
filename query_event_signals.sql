SELECT COUNT(*) as event_signals FROM ml_signals WHERE triggered_by = 'event';
SELECT timestamp, ticker, signal, confidence, triggered_by FROM ml_signals WHERE triggered_by = 'event' ORDER BY timestamp DESC LIMIT 30;
SELECT DATE(timestamp) as date, COUNT(*) as event_count FROM ml_signals WHERE triggered_by = 'event' GROUP BY DATE(timestamp) ORDER BY date DESC LIMIT 20;
SELECT ticker, COUNT(*) as event_count FROM ml_signals WHERE triggered_by = 'event' GROUP BY ticker ORDER BY event_count DESC LIMIT 15;
