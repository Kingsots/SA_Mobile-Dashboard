INSERT INTO ml_signals (timestamp, ticker, interval, signal, confidence, feature_snapshot, model_version, triggered_by)
VALUES (datetime('now'), 'EURUSD', '1h', 1, 0.85, '{"ema21":1}', 'v1.0', 'event:test');
SELECT id, ticker, interval, signal, confidence, triggered_by, timestamp FROM ml_signals ORDER BY id DESC LIMIT 1;