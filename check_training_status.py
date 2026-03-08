#!/usr/bin/env python3
"""Check if model training ran last night"""
import sqlite3
from datetime import datetime

db = '/home/ubuntu/opticore-bot/trading_bot.db'
conn = sqlite3.connect(db)
cursor = conn.cursor()

print("\n" + "="*70)
print("MODEL TRAINING STATUS - Jan 25-26")
print("="*70)

# Get latest training records
cursor.execute("""
SELECT 
    timestamp,
    model_version,
    ROUND(accuracy * 100, 2) as accuracy_pct,
    train_samples,
    deployed
FROM model_training_log
ORDER BY timestamp DESC
LIMIT 10
""")

print("\nLatest Training Records:")
print(f"{'Timestamp':<35} {'Model':<20} {'Accuracy':<12} {'Samples':<10} {'Deploy':<8}")
print("-" * 95)

for row in cursor.fetchall():
    ts = row[0]
    model = row[1]
    acc = f"{row[2]:.2f}%"
    samples = row[3]
    deploy = "✅ YES" if row[4] else "❌ NO"
    print(f"{ts:<35} {model:<20} {acc:<12} {samples:<10} {deploy:<8}")

# Check metadata
import json
import os

metadata_file = '/home/ubuntu/opticore-bot/data/models/model_metadata.json'
if os.path.exists(metadata_file):
    print("\n" + "="*70)
    print("CURRENT MODEL METADATA")
    print("="*70)
    
    with open(metadata_file) as f:
        metadata = json.load(f)
    
    print(f"\nModel File: {metadata.get('model_file', 'N/A')}")
    print(f"Trained At: {metadata.get('trained_at', 'N/A')}")
    
    # Check metrics
    metrics = metadata.get('metrics', {})
    if metrics:
        print(f"\nModel Performance:")
        print(f"  Accuracy:  {metrics.get('accuracy', 'N/A'):.2%}" if isinstance(metrics.get('accuracy'), float) else f"  Accuracy:  {metrics.get('accuracy', 'N/A')}")
        print(f"  Precision: {metrics.get('precision', 'N/A'):.2%}" if isinstance(metrics.get('precision'), float) else f"  Precision: {metrics.get('precision', 'N/A')}")
        print(f"  Recall:    {metrics.get('recall', 'N/A'):.2%}" if isinstance(metrics.get('recall'), float) else f"  Recall:    {metrics.get('recall', 'N/A')}")
        print(f"  F1 Score:  {metrics.get('f1', 'N/A'):.2%}" if isinstance(metrics.get('f1'), float) else f"  F1 Score:  {metrics.get('f1', 'N/A')}")
else:
    print("\n⚠️ model_metadata.json not found")

conn.close()
