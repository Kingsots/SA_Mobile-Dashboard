"""Run immediate data fetch and signal generation"""
import asyncio
from data.tiingo_fetcher import TiingoFetcher
from features.engine import FeatureEngine
from models.xgb_trainer import XGBTrainer
from signals.xgb_signal_engine import XGBSignalEngine
from core.config import Config

async def run_immediate_pipeline():
    print("\n" + "="*70)
    print("  🚀 IMMEDIATE ML PIPELINE RUN")
    print("="*70 + "\n")
    
    # Get all symbols
    symbols = Config.get_symbol_list()
    
    # Step 1: Fetch data for both timeframes
    print("Step 1: Fetching Tiingo data...")
    fetcher = TiingoFetcher()
    
    print("\n📊 Fetching 30m data...")
    results_30m = await fetcher.fetch_batch('30m', symbols)
    print(f"✅ Fetched {len(results_30m)}/{len(symbols)} symbols for 30m")
    
    print("\n📊 Fetching 1h data...")
    results_1h = await fetcher.fetch_batch('1h', symbols)
    print(f"✅ Fetched {len(results_1h)}/{len(symbols)} symbols for 1h")
    
    # Step 2: Generate features
    print("\n" + "="*70)
    print("Step 2: Generating features...")
    print("="*70)
    
    engine = FeatureEngine()
    feature_count = 0
    
    for symbol in symbols:
        for interval in ['30m', '1h']:
            df = engine.generate_features_for_ticker(symbol, interval)
            if df is not None and not df.empty:
                feature_count += 1
                print(f"  ✅ {symbol} {interval}: {len(df)} rows with features")
    
    print(f"\n✅ Generated features for {feature_count} symbol-timeframe pairs")
    
    # Step 3: Train model (if enough data)
    print("\n" + "="*70)
    print("Step 3: Training XGBoost model...")
    print("="*70)
    
    trainer = XGBTrainer()
    model_trained = trainer.train()
    
    if model_trained:
        print("✅ Model trained successfully")
    else:
        print("⚠️  Model training skipped (insufficient data or not needed)")
    
    # Step 4: Generate signals
    print("\n" + "="*70)
    print("Step 4: Generating ML signals...")
    print("="*70)
    
    signal_engine = XGBSignalEngine()
    signal_count = 0
    
    for symbol in symbols:
        for interval in ['30m', '1h']:
            signal = signal_engine.generate_signal(symbol, interval)
            if signal:
                signal_count += 1
                direction = signal['signal']
                confidence = signal['confidence']
                emoji = "🟢" if direction == "BUY" else "🔴" if direction == "SELL" else "⚪"
                print(f"  {emoji} {symbol} {interval}: {direction} ({confidence:.1f}% confidence)")
    
    print(f"\n✅ Generated {signal_count} signals")
    
    print("\n" + "="*70)
    print("  ✅ PIPELINE COMPLETE!")
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(run_immediate_pipeline())
