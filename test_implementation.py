#!/usr/bin/env python3
"""
Quick Test Script - Verify Implementation
Tests core components to ensure everything is working.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("OptiCore Trading Bot - Implementation Test")
print("=" * 60)
print()

# Test 1: Configuration
print("Test 1: Configuration")
print("-" * 60)
try:
    from core.config import Config
    Config.print_config()
    print("✅ Configuration loaded successfully")
except Exception as e:
    print(f"❌ Configuration error: {e}")

print()

# Test 2: CSV Loader
print("Test 2: CSV Loader")
print("-" * 60)
try:
    from data.csv_loader import CSVLoader
    
    loader = CSVLoader()
    summary = loader.get_data_summary()
    
    print(f"Data Directory: {summary['data_dir']}")
    print(f"Available Symbols: {len(summary['symbols'])}")
    print(f"Symbols: {', '.join(summary['symbols'][:5])}...")
    
    if summary['symbols']:
        test_symbol = summary['symbols'][0]
        print(f"\nTesting load for {test_symbol}:")
        timeframes = summary['timeframes_by_symbol'].get(test_symbol, [])
        print(f"  Available timeframes: {', '.join(timeframes)}")
        
        if timeframes:
            test_tf = timeframes[0]
            df = loader.load_csv(test_symbol, test_tf)
            if df is not None:
                print(f"  ✅ Loaded {len(df)} records for {test_symbol} {test_tf}")
            else:
                print(f"  ⚠️ Could not load {test_symbol} {test_tf}")
    
    print("✅ CSV Loader working")
except Exception as e:
    print(f"❌ CSV Loader error: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 3: Technical Indicators
print("Test 3: Technical Indicators")
print("-" * 60)
try:
    from core.indicators import TechnicalIndicators
    from data.csv_loader import CSVLoader
    
    loader = CSVLoader()
    summary = loader.get_data_summary()
    
    if summary['symbols']:
        test_symbol = summary['symbols'][0]
        timeframes = summary['timeframes_by_symbol'].get(test_symbol, [])
        
        if timeframes:
            test_tf = timeframes[0]
            df = loader.load_csv(test_symbol, test_tf)
            
            if df is not None and not df.empty:
                indicators = TechnicalIndicators.calculate_all_indicators(df)
                print(f"Calculated indicators for {test_symbol} {test_tf}:")
                print(f"  EMA(21): {indicators.get('ema', 0):.2f}")
                print(f"  RSI(14): {indicators.get('rsi', 0):.1f}")
                print(f"  Price: {indicators.get('current_price', 0):.2f}")
                print(f"  Volume: {indicators.get('current_volume', 0):,.0f}")
                print(f"  Bullish Engulfing: {indicators.get('bullish_engulfing', False)}")
                print(f"  Bearish Engulfing: {indicators.get('bearish_engulfing', False)}")
                print("✅ Technical Indicators working")
            else:
                print("⚠️ No data available for indicator test")
    else:
        print("⚠️ No symbols available for indicator test")
        
except Exception as e:
    print(f"❌ Technical Indicators error: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 4: Multi-Timeframe Analyzer
print("Test 4: Multi-Timeframe Analyzer")
print("-" * 60)
try:
    from core.multi_timeframe import MultiTimeframeAnalyzer
    from data.csv_loader import CSVLoader
    
    loader = CSVLoader()
    analyzer = MultiTimeframeAnalyzer()
    summary = loader.get_data_summary()
    
    if summary['symbols']:
        test_symbol = summary['symbols'][0]
        
        # Load all available timeframes
        timeframe_data = loader.load_all_timeframes(test_symbol)
        
        if timeframe_data:
            print(f"Analyzing cascade for {test_symbol}:")
            cascade_result = analyzer.analyze_cascade(timeframe_data)
            
            print(f"  Aligned: {cascade_result['aligned']}")
            print(f"  Direction: {cascade_result['direction']}")
            print(f"  Valid Timeframes: {cascade_result['valid_timeframes']}/{len(Config.CASCADE_TIMEFRAMES)}")
            
            for tf in Config.CASCADE_TIMEFRAMES:
                if tf in cascade_result['cascade']:
                    tf_data = cascade_result['cascade'][tf]
                    if tf_data['valid']:
                        print(f"    {tf.upper()}: {tf_data['trend'].upper()}")
            
            print("✅ Multi-Timeframe Analyzer working")
        else:
            print("⚠️ No timeframe data available")
    else:
        print("⚠️ No symbols available")
        
except Exception as e:
    print(f"❌ Multi-Timeframe Analyzer error: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 5: Strategy
print("Test 5: OptiCore Strategy")
print("-" * 60)
try:
    from strategies.opticore_strategy import OptiCoreStrategy
    from data.csv_loader import CSVLoader
    
    loader = CSVLoader()
    strategy = OptiCoreStrategy()
    summary = loader.get_data_summary()
    
    if summary['symbols']:
        test_symbol = summary['symbols'][0]
        timeframe_data = loader.load_all_timeframes(test_symbol)
        
        if '1h' in timeframe_data or '30m' in timeframe_data:
            test_tf = '1h' if '1h' in timeframe_data else '30m'
            
            print(f"Analyzing {test_symbol} on {test_tf}:")
            result = strategy.analyze_symbol(test_symbol, test_tf, timeframe_data)
            
            print(f"  Signal: {result['signal']}")
            print(f"  Confidence: {result.get('confidence', 0):.1f}%")
            
            if 'entry_analysis' in result:
                entry = result['entry_analysis']
                if 'conditions_met' in entry:
                    print(f"  Entry Conditions:")
                    for condition, met in entry['conditions_met'].items():
                        icon = "✅" if met else "❌"
                        print(f"    {icon} {condition}")
            
            print("✅ OptiCore Strategy working")
        else:
            print("⚠️ No 1h or 30m data available for strategy test")
    else:
        print("⚠️ No symbols available")
        
except Exception as e:
    print(f"❌ OptiCore Strategy error: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)
print("Test Complete")
print("=" * 60)
print()
print("Summary:")
print("  ✅ = Working correctly")
print("  ⚠️  = Partial/Missing data (not an error)")
print("  ❌ = Error occurred")
print()
print("If you see any ❌, review the error messages above.")
print("If you see ⚠️, you may need to run: python generate_30m_data.py")
print()
