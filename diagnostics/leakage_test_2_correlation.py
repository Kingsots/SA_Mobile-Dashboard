"""
DIAGNOSTIC TEST 2: Target Correlation Analysis

Load latest feature data from features table and compute correlation with target.
Target = 1 if next_close > close, else -1

Flag any feature with |correlation| > 0.7 as SEVERE LEAKAGE.
Flag any feature with |correlation| > 0.5 as MODERATE LEAKAGE.
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path

print("=" * 70)
print("DIAGNOSTIC TEST 2: TARGET CORRELATION ANALYSIS")
print("=" * 70)

# Connect to database
db_path = Path("trading_bot.db")
if not db_path.exists():
    print(f"❌ Database not found at {db_path}")
    exit(1)

try:
    conn = sqlite3.connect(str(db_path))
    print(f"✅ Connected to database: {db_path}")
except Exception as e:
    print(f"❌ Error connecting to database: {e}")
    exit(1)

# Load features for a single symbol (AUDCAD, 1h, last 1000 rows)
try:
    query = """
    SELECT * FROM features 
    WHERE ticker = 'AUDCAD' AND interval = '1h' 
    ORDER BY timestamp DESC 
    LIMIT 1000
    """
    df = pd.read_sql_query(query, conn)
    print(f"✅ Loaded {len(df)} feature rows for AUDCAD 1h")
except Exception as e:
    print(f"❌ Error loading features: {e}")
    conn.close()
    exit(1)

conn.close()

# Reconstruct target (next bar direction)
try:
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['next_close'] = df['close'].shift(-1)
    df['target'] = np.where(df['next_close'] > df['close'], 1, -1)
    df = df.dropna()
    print(f"✅ Target constructed ({len(df)} valid rows)")
except Exception as e:
    print(f"❌ Error constructing target: {e}")
    exit(1)

# Feature columns
feature_cols = ['open', 'high', 'low', 'close', 'ema_21', 'ema_100', 'rsi_14',
                'volume', 'volume_sma_20', 'volume_ratio', 'obv', 'ad', 'vwap', 'vwap_slope']

# Filter to available columns
available_cols = [col for col in feature_cols if col in df.columns]
print(f"✅ Computing correlation for {len(available_cols)} features")

# Compute correlations
try:
    correlations = df[available_cols + ['target']].corr()['target'].drop('target').sort_values(ascending=False)
except Exception as e:
    print(f"❌ Error computing correlations: {e}")
    exit(1)

# Display all correlations
print("\n" + "=" * 70)
print("FEATURE CORRELATIONS WITH TARGET")
print("=" * 70)
print(f"{'Feature':<20} {'Correlation':>12} {'Risk Level':>15}")
print("-" * 70)

severe_leakage = []
moderate_leakage = []

for feat, corr in correlations.items():
    abs_corr = abs(corr)
    
    if abs_corr > 0.7:
        risk = "🚨 SEVERE"
        severe_leakage.append((feat, corr))
    elif abs_corr > 0.5:
        risk = "⚠️  MODERATE"
        moderate_leakage.append((feat, corr))
    elif abs_corr > 0.3:
        risk = "⚠️  MILD"
    else:
        risk = "✅ SAFE"
    
    print(f"{feat:<20} {corr:>12.4f} {risk:>15}")

# Summary
print("\n" + "=" * 70)
print("LEAKAGE SUMMARY")
print("=" * 70)

if severe_leakage:
    print(f"\n🚨 SEVERE LEAKAGE ({len(severe_leakage)} features):")
    for feat, corr in severe_leakage:
        print(f"   {feat}: {corr:.4f}")

if moderate_leakage:
    print(f"\n⚠️  MODERATE LEAKAGE ({len(moderate_leakage)} features):")
    for feat, corr in moderate_leakage:
        print(f"   {feat}: {corr:.4f}")

if not severe_leakage and not moderate_leakage:
    print("\n✅ No severe or moderate leakage detected!")

print("\n" + "=" * 70)
print("INTERPRETATION")
print("=" * 70)
print("""
CORRELATION THRESHOLDS:
  |corr| > 0.7  → SEVERE LEAKAGE (direct relationship)
  |corr| > 0.5  → MODERATE LEAKAGE (strong relationship)
  |corr| > 0.3  → MILD LEAKAGE (noticeable relationship)
  |corr| < 0.3  → SAFE (weak relationship)

EXPECTED RESULTS FOR LEAKED MODEL:
  - close, high, low      → Very high correlation (>0.8)
  - obv, ad, vwap         → High correlation (>0.6)
  - ema_21, ema_100, rsi  → Low correlation (<0.3)

If high-risk features show high correlation:
  ❌ Model is using current price to predict next price
  ❌ This is circular logic, not tradeable
  
Action: Remove features with |corr| > 0.5, retrain.
""")
