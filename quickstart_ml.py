"""
Quick feature generation + model training to get system operational
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import asyncio
import logging
from features.engine import FeatureEngine
from models.xgb_trainer import XGBTrainer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def quickstart():
    """Generate features and train model"""
    
    print("\n" + "="*70)
    print("  🚀 QUICKSTART: Features + Model Training")
    print("="*70)
    
    # 1. Generate features
    print("\n1️⃣  Generating features for all symbols (1h)...")
    try:
        engine = FeatureEngine()
        results = engine.process_all_tickers('1h')
        print(f"   ✅ Features generated: {len(results)} symbols")
        for ticker, count in results.items():
            print(f"      {ticker:8s}: {count} records")
    except Exception as e:
        print(f"   ❌ Feature generation failed: {e}")
        return False
    
    # 2. Train model
    print("\n2️⃣  Training XGBoost model...")
    try:
        trainer = XGBTrainer()
        model = trainer.train_pipeline(interval='1h', days=90)
        
        if model:
            print(f"   ✅ Model trained and deployed")
        else:
            print(f"   ⚠️  Model not deployed (check accuracy threshold)")
            return False
    except Exception as e:
        print(f"   ❌ Model training failed: {e}")
        return False
    
    print("\n" + "="*70)
    print("  ✅ QUICKSTART COMPLETE")
    print("  💡 ML signals will generate at next :05 (e.g., 16:05, 17:05)")
    print("="*70)
    print()
    
    return True

if __name__ == '__main__':
    success = quickstart()
    exit(0 if success else 1)
