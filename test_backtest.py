"""
Quick Backtest Test
Run backtest on single symbol to validate implementation.
"""

import sys
sys.path.insert(0, '.')

from backtest.engine import BacktestEngine
from backtest.metrics import PerformanceMetrics

print("🚀 Running OptiCore Backtest Test...")
print("=" * 70)
print("Testing: XAUUSD (Gold) on 1h timeframe")
print("=" * 70)
print()

# Run backtest on single symbol
engine = BacktestEngine(lookback_days=90)
results = engine.run_backtest(symbols=['XAUUSD'], timeframes=['1h'])

print()
print("📊 Calculating Performance Metrics...")
print()

# Calculate metrics
calc = PerformanceMetrics()
metrics = calc.calculate_all_metrics(results)

# Print report
print(calc.format_metrics_report(metrics))

# Save to database
print("💾 Saving metrics to database...")
calc.save_metrics_to_db(metrics)

print()
print("✅ Backtest test complete!")
