"""
Quick Backtest with CSV Data Only
Test backtest on symbols with complete CSV data.
"""

import sys
sys.path.insert(0, '.')

from backtest.engine import BacktestEngine
from backtest.metrics import PerformanceMetrics

print("🚀 Running OptiCore Backtest with CSV Data")
print("=" * 70)
print("Note: Using only symbols with available CSV files")
print("=" * 70)
print()

# Symbols with 1h CSV data available
test_symbols = ['EURUSD', 'GBPUSD', 'USDJPY']

# Run backtest
engine = BacktestEngine(lookback_days=30)  # Shorter period for testing
results = engine.run_backtest(symbols=test_symbols, timeframes=['1h'])

print()
print("📊 Calculating Performance Metrics...")
print()

# Calculate metrics
calc = PerformanceMetrics()
metrics = calc.calculate_all_metrics(results)

# Print report
print(calc.format_metrics_report(metrics))

# Print some trade details if available
if results['trades']:
    print("\n📋 SAMPLE TRADES (First 5):")
    print("=" * 70)
    for i, trade in enumerate(results['trades'][:5], 1):
        print(f"\nTrade #{i}:")
        print(f"  Symbol: {trade['symbol']} | Signal: {trade['signal']}")
        print(f"  Entry: {trade['entry_price']:.5f} @ {trade['entry_time']}")
        print(f"  Exit:  {trade['exit_price']:.5f} @ {trade['exit_time']}")
        print(f"  Profit: {trade['profit']:+.2f}% | Reason: {trade['exit_reason']}")
        print(f"  Confidence: {trade['confidence']:.1f}%")

# Save to database
print("\n💾 Saving metrics to database...")
calc.save_metrics_to_db(metrics)

print()
print("✅ Backtest complete!")
print(f"   Total trades: {results['total_trades']}")
print(f"   Duration: {results['duration']:.1f} seconds")
