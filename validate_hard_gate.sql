-- Hard Gate Validation Report
-- Window: 2026-02-18 11:57:19 to now

.mode list
.separator |

-- [1] SIGNAL DISTRIBUTION
.print ============================================================
.print [1] SIGNAL DISTRIBUTION
.print ============================================================

SELECT 
    COUNT(*) as total_signals,
    SUM(CASE WHEN signal_type='BUY' THEN 1 ELSE 0 END) as buy_count,
    SUM(CASE WHEN signal_type='SELL' THEN 1 ELSE 0 END) as sell_count,
    SUM(CASE WHEN signal_type='NEUTRAL' THEN 1 ELSE 0 END) as neutral_count,
    ROUND(100.0*SUM(CASE WHEN signal_type='BUY' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0), 1) as buy_pct,
    ROUND(100.0*SUM(CASE WHEN signal_type='SELL' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0), 1) as sell_pct,
    ROUND(100.0*SUM(CASE WHEN signal_type='NEUTRAL' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0), 1) as neutral_pct,
    COUNT(DISTINCT symbol) as unique_symbols,
    COUNT(DISTINCT timeframe) as unique_intervals
FROM signals 
WHERE timestamp >= '2026-02-18 11:57:19';

-- [2] CONFIDENCE STATISTICS
.print 
.print ============================================================
.print [2] CONFIDENCE STATISTICS BY CLASS
.print ============================================================

SELECT 
    signal_type,
    COUNT(*) as count,
    ROUND(AVG(confidence), 4) as mean_conf,
    ROUND(MIN(confidence), 4) as min_conf,
    ROUND(MAX(confidence), 4) as max_conf
FROM signals
WHERE timestamp >= '2026-02-18 11:57:19'
GROUP BY signal_type
ORDER BY signal_type;

-- [3] Recent Signals Sample
.print 
.print ============================================================
.print [3] LAST 10 SIGNALS
.print ============================================================

SELECT 
    timestamp,
    symbol,
    signal_type,
    ROUND(confidence, 4) as confidence
FROM signals
WHERE timestamp >= '2026-02-18 11:57:19'
ORDER BY timestamp DESC
LIMIT 10;
