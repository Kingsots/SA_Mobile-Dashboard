#!/usr/bin/env python3
"""Check current model status on EC2"""
import json
import sqlite3
from pathlib import Path

db_path = '/home/ubuntu/opticore-bot/trading_bot.db'
models_dir = Path('/home/ubuntu/opticore-bot/data/models')

try:
    # Get latest model files
    pkl_files = sorted(models_dir.glob('*.pkl'), reverse=True)[:5]
    print("\n=== LATEST MODELS ===")
    for f in pkl_files:
        print(f"  {f.name} ({f.stat().st_size / 1024:.1f} KB)")
    
    # Get metadata
    metadata_file = models_dir / 'model_metadata.json'
    if metadata_file.exists():
        with open(metadata_file) as f:
            metadata = json.load(f)
        print("\n=== CURRENT MODEL METADATA ===")
        print(f"  Model: {metadata.get('model_file', 'N/A')}")
        print(f"  Accuracy: {metadata.get('accuracy', 'N/A'):.2%}" if isinstance(metadata.get('accuracy'), float) else f"  Accuracy: {metadata.get('accuracy', 'N/A')}")
        print(f"  Trained: {metadata.get('trained_at', 'N/A')}")
        print(f"  Samples: {metadata.get('training_samples', 'N/A')}")
    
    # Get training log
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp, model_file, accuracy, training_samples 
        FROM model_training_log 
        ORDER BY timestamp DESC 
        LIMIT 5
    """)
    print("\n=== TRAINING HISTORY (Last 5) ===")
    for row in cursor.fetchall():
        timestamp, model_file, accuracy, samples = row
        print(f"  {timestamp} | {model_file} | Acc: {accuracy:.2%} | Samples: {samples}")
    
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
