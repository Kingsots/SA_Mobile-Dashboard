"""
Tiingo + ML Pipeline Test Suite
Test all components of the upgraded system
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config import Config
from core.database import DatabaseManager
from data.tiingo_fetcher import TiingoFetcher
from features.engine import FeatureEngine
from models.xgb_trainer import XGBTrainer
from signals.xgb_signal_engine import XGBSignalEngine


def print_section(title: str):
    """Print formatted section header"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def test_database_migration():
    """Test 1: Verify database migration"""
    print_section("TEST 1: Database Migration")
    
    db = DatabaseManager()
    db.run_migrations()
    
    # Check new tables exist
    import sqlite3
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    required_tables = [
        'ohlcv_data',
        'signals',
        'performance_metrics',
        'ml_signals',
        'ohlcv_raw',
        'features',
        'api_usage',
        'model_training_log',
        'rate_limits'
    ]
    
    print("Required Tables:")
    for table in required_tables:
        exists = table in tables
        status = "✅" if exists else "❌"
        print(f"   {status} {table}")
    
    cursor.execute("PRAGMA table_info(ml_signals)")
    ml_columns = [row[1] for row in cursor.fetchall()]
    has_triggered_by = 'triggered_by' in ml_columns
    print(f"Triggered_by column present: {'✅' if has_triggered_by else '❌'}")
    
    conn.close()
    
    all_exist = all(table in tables for table in required_tables)
    return all_exist and has_triggered_by


async def test_tiingo_fetcher():
    """Test 2: Tiingo API fetcher"""
    print_section("TEST 2: Tiingo Fetcher")
    
    async with TiingoFetcher() as fetcher:
        # Test single symbol fetch
        print("Testing single symbol fetch (EURUSD)...")
        df = await fetcher.fetch_price('EURUSD', '1h')
        
        if df is not None:
            print(f"✅ Fetched {len(df)} candles for EURUSD")
            print(f"\nSample data:")
            print(df.head(3))
            return True
        else:
            print(f"❌ Failed to fetch EURUSD data")
            return False


def test_feature_engineering():
    """Test 3: Feature engineering"""
    print_section("TEST 3: Feature Engineering")
    
    engine = FeatureEngine()
    
    # Generate features for test symbol
    print("Generating features for EURUSD (1h)...")
    df_features = engine.generate_features_for_ticker('EURUSD', '1h', days=30)
    
    if df_features is not None:
        print(f"✅ Generated {len(df_features)} feature rows")
        print(f"\nFeature columns:")
        for col in df_features.columns:
            print(f"   - {col}")
        
        # Save to database
        engine.save_features_to_db('EURUSD', '1h', df_features)
        
        return True
    else:
        print(f"❌ Feature generation failed")
        return False


def test_model_training():
    """Test 4: XGBoost model training"""
    print_section("TEST 4: Model Training")
    
    trainer = XGBTrainer()
    
    # Train model on 1h data
    print("Training model on 1h data (90 days)...")
    model = trainer.train_pipeline(ticker=None, interval='1h', days=90)
    
    if model is not None:
        print(f"✅ Model trained successfully")
        return True
    else:
        print(f"⚠️  Model training completed but may not have met accuracy threshold")
        return False


def test_signal_generation():
    """Test 5: Signal generation"""
    print_section("TEST 5: Signal Generation")
    
    engine = XGBSignalEngine()
    
    if engine.model is None:
        print(f"⚠️  No deployed model found - skipping signal generation test")
        return False
    
    # Generate signals for test symbols
    test_symbols = ['EURUSD', 'GBPUSD', 'USDJPY']
    print(f"Generating signals for {len(test_symbols)} symbols...")
    
    signals = engine.generate_signals('1h', symbols=test_symbols)
    
    if signals:
        print(f"\n✅ Generated {len(signals)} signals")
        
        # Show sample
        print(f"\nSample signals:")
        for signal in signals[:3]:
            print(f"   {signal['ticker']:10} {signal['signal_label']:8} (conf: {signal['confidence']:.1%})")
        
        return True
    else:
        print(f"❌ Signal generation failed")
        return False


def test_database_methods():
    """Test 6: Database ML methods"""
    print_section("TEST 6: Database ML Methods")
    
    db = DatabaseManager()
    
    # Test save_raw_ohlcv
    print("Testing save_raw_ohlcv...")
    test_candle = {
        'timestamp': '2025-01-01 00:00:00',
        'open': 1.1000,
        'high': 1.1050,
        'low': 1.0950,
        'close': 1.1025,
        'volume': 1000
    }
    db.save_raw_ohlcv('TEST', '1h', test_candle, 'test')
    print("   ✅ save_raw_ohlcv")
    
    # Test save_features
    print("Testing save_features...")
    test_features = {
        'open': 1.1000,
        'high': 1.1050,
        'low': 1.0950,
        'close': 1.1025,
        'volume': 1000,
        'ema_21': 1.1000,
        'ema_100': 1.0900,
        'rsi_14': 55.0,
        'obv': 5000,
        'ad': 1000,
        'vwap': 1.1010,
        'vwap_slope': 0.0005,
        'volume_sma_20': 950,
        'volume_ratio': 1.05
    }
    db.save_features('TEST', '2025-01-01 00:00:00', '1h', test_features)
    print("   ✅ save_features")
    
    # Test save_ml_signal
    print("Testing save_ml_signal...")
    db.save_ml_signal('TEST', '2025-01-01 00:00:00', '1h', 1, 0.75, '{}', 'v1', triggered_by='unit_test')
    print("   ✅ save_ml_signal")
    
    # Test log_api_usage
    print("Testing log_api_usage...")
    db.log_api_usage('tiingo', 'test_endpoint', 'TEST', '1h', True)
    print("   ✅ log_api_usage")
    
    return True


def test_configuration():
    """Test 7: Configuration settings"""
    print_section("TEST 7: Configuration")
    
    print("Tiingo Configuration:")
    print(f"   Token: {Config.TIINGO_API_TOKEN[:20]}...")
    print(f"   Base URL: {Config.TIINGO_BASE_URL}")
    print(f"   Hourly Limit: {Config.TIINGO_MAX_HOURLY_REQUESTS}")
    print(f"   Daily Limit: {Config.TIINGO_MAX_DAILY_REQUESTS}")
    
    print("\nML Configuration:")
    print(f"   Train Lookback: {Config.ML_TRAIN_LOOKBACK_DAYS} days")
    print(f"   Target Accuracy: {Config.ML_TARGET_ACCURACY:.0%}")
    print(f"   XGBoost N Estimators: {Config.XGBOOST_N_ESTIMATORS}")
    print(f"   XGBoost Max Depth: {Config.XGBOOST_MAX_DEPTH}")
    print(f"   XGBoost Learning Rate: {Config.XGBOOST_LEARNING_RATE}")
    
    print("\nPipeline Settings:")
    print(f"   USE_TIINGO_PIPELINE: {Config.USE_TIINGO_PIPELINE}")
    print(f"   Data Source Priority: {Config.DATA_SOURCE_PRIORITY}")
    
    print("\nWatchlist:")
    symbols = Config.get_symbol_list()
    print(f"   {len(symbols)} symbols: {', '.join(symbols)}")
    
    return True


async def run_all_tests():
    """Run complete test suite"""
    print("\n" + "="*70)
    print("  🧪 TIINGO + ML PIPELINE TEST SUITE")
    print("="*70)
    
    results = {}
    
    # Test 1: Database migration
    try:
        results['database_migration'] = test_database_migration()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        results['database_migration'] = False
    
    # Test 2: Tiingo fetcher
    try:
        results['tiingo_fetcher'] = await test_tiingo_fetcher()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        results['tiingo_fetcher'] = False
    
    # Test 3: Feature engineering
    try:
        results['feature_engineering'] = test_feature_engineering()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        results['feature_engineering'] = False
    
    # Test 4: Model training
    try:
        results['model_training'] = test_model_training()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        results['model_training'] = False
    
    # Test 5: Signal generation
    try:
        results['signal_generation'] = test_signal_generation()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        results['signal_generation'] = False
    
    # Test 6: Database methods
    try:
        results['database_methods'] = test_database_methods()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        results['database_methods'] = False
    
    # Test 7: Configuration
    try:
        results['configuration'] = test_configuration()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        results['configuration'] = False
    
    # Summary
    print_section("TEST SUMMARY")
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status:10} {test_name}")
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    print(f"\n{'='*70}")
    print(f"  RESULTS: {passed_tests}/{total_tests} tests passed")
    print(f"{'='*70}\n")
    
    return passed_tests == total_tests


if __name__ == '__main__':
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
