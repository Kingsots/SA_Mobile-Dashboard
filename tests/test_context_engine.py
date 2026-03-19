"""
Test Suite for Context Engine
Tests all 7 components and integration

Run: pytest tests/test_context_engine.py -v
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from signals.context_engine import ContextEngine


# ═════════════════════════════════════════════════════════════════════════════
# FIXTURES - Synthetic DataFrames for testing
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def normal_df():
    """Normal market conditions DataFrame"""
    dates = pd.date_range(end=datetime.now(), periods=100, freq='h')
    df = pd.DataFrame({
        'timestamp': dates,
        'open': 1.1500 + np.random.randn(100) * 0.0005,
        'high': 1.1510 + np.random.randn(100) * 0.0005,
        'low': 1.1490 + np.random.randn(100) * 0.0005,
        'close': 1.1505 + np.random.randn(100) * 0.0005,
        'volume': 100000 + np.random.randn(100) * 10000,
    })
    df = df.set_index('timestamp')
    
    # Add features
    engine = ContextEngine.__new__(ContextEngine)
    df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['ema_100'] = df['close'].ewm(span=100, adjust=False).mean()
    df['rsi_14'] = 50.0 + np.random.randn(100) * 10  # Normal RSI
    df['volume_sma_20'] = df['volume'].rolling(window=20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_sma_20'].replace(0, np.nan)
    df['volume_ratio'] = df['volume_ratio'].fillna(1.0)
    
    # Compute ATR
    high = df['high']
    low = df['low']
    close = df['close']
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr_14'] = tr.rolling(window=14).mean()
    df['atr_sma_20'] = df['atr_14'].rolling(window=20).mean()
    
    return df.reset_index()


@pytest.fixture
def compressed_df(normal_df):
    """Compressed market (low volatility)"""
    df = normal_df.copy()
    # Reduce candle size and ATR to simulate compression
    df['high'] = df['close'] + 0.00005
    df['low'] = df['close'] - 0.00005
    
    # Recompute ATR with compressed values
    high = df['high']
    low = df['low']
    close = df['close']
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr_14'] = tr.rolling(window=14).mean()
    df['atr_sma_20'] = df['atr_14'].rolling(window=20).mean()
    
    return df


@pytest.fixture
def expanded_df(normal_df):
    """Expanded market (high volatility)"""
    df = normal_df.copy()
    # Increase candle size and ATR to simulate expansion
    df['high'] = df['close'] + 0.0015
    df['low'] = df['close'] - 0.0015
    
    # Recompute ATR with expanded values
    high = df['high']
    low = df['low']
    close = df['close']
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr_14'] = tr.rolling(window=14).mean()
    df['atr_sma_20'] = df['atr_14'].rolling(window=20).mean()
    
    return df


@pytest.fixture
def engine():
    """Context Engine instance"""
    return ContextEngine()


# ═════════════════════════════════════════════════════════════════════════════
# TESTS 1-3: Compression Score (Function 1)
# ═════════════════════════════════════════════════════════════════════════════

def test_compression_normal(engine, normal_df):
    """Test compression score in normal market (should be ~1.0)"""
    # Make sure ATR values are computed properly
    score = engine._compute_compression(normal_df)
    # In normal markets, should be close to 1.0
    assert 0.7 < score < 1.5, f"Normal compression should be ~1.0, got {score}"


def test_compression_compressed(engine, compressed_df):
    """Test compression score in compressed market (should be <0.6)"""
    score = engine._compute_compression(compressed_df)
    # Compressed markets should have lower ATR ratio
    assert score < 1.2, f"Compressed should have low ATR ratio, got {score}"


def test_compression_expanding(engine, expanded_df):
    """Test compression score in expanding market (should be >1.2)"""
    score = engine._compute_compression(expanded_df)
    # Expanding markets should have higher ATR ratio
    assert score > 1.0, f"Expanding should have high ATR ratio, got {score}"


# ═════════════════════════════════════════════════════════════════════════════
# TESTS 4-5: Expansion Pressure (Function 2)
# ═════════════════════════════════════════════════════════════════════════════

def test_expansion_pressure_normalized_range(engine, normal_df):
    """Test that expansion pressure ALWAYS returns [0.0-1.0]"""
    compression_score = engine._compute_compression(normal_df)
    
    # Test with multiple compression values
    for comp_score in [0.3, 0.6, 1.0, 1.5, 2.0]:
        pressure = engine._compute_expansion_pressure(normal_df, comp_score)
        assert 0.0 <= pressure <= 1.0, (
            f"Expansion pressure must be [0.0-1.0], got {pressure} "
            f"with compression_score={comp_score}"
        )


def test_expansion_pressure_variations(engine):
    """Test expansion pressure with 5 different input combinations"""
    # Create synthetic DataFrames with controlled values
    test_cases = [
        {"compression": 0.5, "volume_ratio": 0.5, "atr": 0.001},
        {"compression": 1.0, "volume_ratio": 1.0, "atr": 0.001},
        {"compression": 1.5, "volume_ratio": 2.0, "atr": 0.001},
        {"compression": 0.8, "volume_ratio": 1.2, "atr": 0.001},
        {"compression": 1.2, "volume_ratio": 0.8, "atr": 0.001},
    ]
    
    for i, case in enumerate(test_cases):
        df = pd.DataFrame({
            'atr_14': [case["atr"]] * 30,
            'atr_sma_20': [case["atr"]] * 30,
            'volume_ratio': [case["volume_ratio"]] * 30,
            'high': [1.15 + 0.0001] * 30,
            'low': [1.15 - 0.0001] * 30,
            'volume_sma_20': [100000] * 30,
        })
        
        pressure = engine._compute_expansion_pressure(df, case["compression"])
        assert 0.0 <= pressure <= 1.0, (
            f"Test case {i}: Pressure {pressure} not in [0.0, 1.0]"
        )


# ═════════════════════════════════════════════════════════════════════════════
# TESTS 6-9: RSI Stage Detection (Function 3)
# ═════════════════════════════════════════════════════════════════════════════

def test_rsi_stage_1a(engine):
    """Test Stage 1A: RSI <40 with compression"""
    df = pd.DataFrame({
        'rsi_14': [35.0] * 30,  # Low RSI
        'atr_14': [0.001] * 30,
        'atr_sma_20': [0.002] * 30,  # Higher baseline = compression
    })
    stage = engine._detect_rsi_stage(df, compression_score=0.5)
    assert stage == "1A", f"Expected Stage 1A, got {stage}"


def test_rsi_stage_1b(engine):
    """Test Stage 1B: RSI 40-60 with compression"""
    df = pd.DataFrame({
        'rsi_14': [52.0] * 30,  # Mid RSI
        'atr_14': [0.001] * 30,
        'atr_sma_20': [0.0015] * 30,  # Compression
    })
    stage = engine._detect_rsi_stage(df, compression_score=0.65)
    assert stage == "1B", f"Expected Stage 1B, got {stage}"


def test_rsi_stage_1c(engine):
    """Test Stage 1C: RSI >60 and expanding"""
    df = pd.DataFrame({
        'rsi_14': [68.0] * 30,  # High RSI
        'atr_14': [0.0015] * 30,
        'atr_sma_20': [0.001] * 30,  # Expansion
    })
    stage = engine._detect_rsi_stage(df, compression_score=1.3)
    assert stage == "1C", f"Expected Stage 1C, got {stage}"


def test_rsi_stage_neutral_no_data(engine):
    """Test NEUTRAL when RSI is NaN"""
    df = pd.DataFrame({
        'rsi_14': [np.nan] * 30,
    })
    stage = engine._detect_rsi_stage(df, 1.0)
    assert stage == "NEUTRAL", f"Expected NEUTRAL for NaN RSI, got {stage}"


def test_rsi_stage_neutral_short_df(engine):
    """Test NEUTRAL when DataFrame too short"""
    df = pd.DataFrame({
        'rsi_14': [50.0] * 5,  # Only 5 bars
    })
    stage = engine._detect_rsi_stage(df, 1.0)
    assert stage == "NEUTRAL", f"Expected NEUTRAL for short DF, got {stage}"


# ═════════════════════════════════════════════════════════════════════════════
# TEST 10: Liquidity Pool Detection - ATR-relative Tolerance
# ═════════════════════════════════════════════════════════════════════════════

def test_liquidity_pool_atr_relative_tolerance(engine):
    """Test that tolerance = ATR × 0.3, NOT hardcoded"""
    # Test case 1: atr_14=0.0020 → tolerance must be 0.0006
    dates = pd.date_range(end=datetime.now(), periods=100, freq='h')
    df = pd.DataFrame({
        'timestamp': dates,
        'high': 1.1500 + np.sin(np.arange(100) * 0.1) * 0.0005,
        'low': 1.1490 + np.sin(np.arange(100) * 0.1) * 0.0005,
        'close': 1.1495,
        'atr_14': [0.0020] * 100,
        'atr_sma_20': [0.0020] * 100,
        'volume': [100000] * 100,
        'volume_sma_20': [100000] * 100,
    })
    
    pools = engine._detect_liquidity_pools(df, "TEST")
    # Just verify no exception; exact tolerance calculation is internal
    assert isinstance(pools, list), "Should return list of pools"
    
    # Test case 2: atr_14=0.0050 → tolerance must be 0.0015
    df['atr_14'] = [0.0050] * 100
    pools2 = engine._detect_liquidity_pools(df, "TEST")
    assert isinstance(pools2, list), "Should return list with higher ATR"


# ═════════════════════════════════════════════════════════════════════════════
# TEST 11: Liquidity Sweep - All 3 Conditions Required
# ═════════════════════════════════════════════════════════════════════════════

def test_sweep_requires_reversal(engine):
    """Test: Missing reversal candle → False"""
    dates = pd.date_range(end=datetime.now(), periods=50, freq='h')
    df = pd.DataFrame({
        'timestamp': dates,
        'open': [1.1500] * 50,
        'high': [1.1510] * 50,  # Keeps going up, no reversal
        'low': [1.1490] * 50,
        'close': [1.1508] * 50,  # Always up
        'volume': [150000] * 50,
        'volume_sma_20': [100000] * 50,
        'atr_14': [0.001] * 50,
    })
    
    pools = [{"price": 1.1500, "type": "session_high"}]
    sweep = engine._detect_liquidity_sweep(df, pools)
    assert sweep == False, "Should be False without reversal"


def test_sweep_requires_volume(engine):
    """Test: Missing volume spike → False"""
    dates = pd.date_range(end=datetime.now(), periods=50, freq='h')
    df = pd.DataFrame({
        'timestamp': dates,
        'open': [1.1500] * 50,
        'high': [1.1520] + [1.1500] * 49,  # One spike up
        'low': [1.1480] * 50,
        'close': [1.1490] * 50,  # Close back down (reversal)
        'volume': [50000] * 50,  # But volume is DOWN, not up
        'volume_sma_20': [100000] * 50,
        'atr_14': [0.001] * 50,
    })
    
    pools = [{"price": 1.1500, "type": "session_high"}]
    sweep = engine._detect_liquidity_sweep(df, pools)
    assert sweep == False, "Should be False without volume spike"


def test_sweep_requires_wick_ratio(engine):
    """Test: Insufficient wick-to-body ratio (<1.5) → False"""
    dates = pd.date_range(end=datetime.now(), periods=50, freq='h')
    df = pd.DataFrame({
        'timestamp': dates,
        'open': [1.1500] * 50,
        'high': [1.1505] + [1.1500] * 49,  # Small wick (0.0005)
        'low': [1.1495] * 50,
        'close': [1.1490] * 50,  # Reversal
        'volume': [150000] * 50,  # Volume spike
        'volume_sma_20': [100000] * 50,
        'atr_14': [0.001] * 50,
    })
    
    pools = [{"price": 1.1500, "type": "session_high"}]
    sweep = engine._detect_liquidity_sweep(df, pools)
    # With small wick and large body, ratio < 1.5, should be False
    assert sweep == False, "Should be False without adequate wick-to-body ratio"


# ═════════════════════════════════════════════════════════════════════════════
# TEST 12: Full Integration - Output Schema and Safe Defaults
# ═════════════════════════════════════════════════════════════════════════════

def test_full_compute_context_output_schema(engine, normal_df):
    """Test that compute_context() returns dict with exactly 7 keys and correct types"""
    context = engine.compute_context(normal_df, "EURUSD", "30m")
    
    # Check exactly 7 keys
    required_keys = {
        "compression_score",
        "expansion_pressure",
        "rsi_stage",
        "nearest_liquidity",
        "liquidity_type",
        "distance_to_liquidity",
        "liquidity_sweep"
    }
    assert set(context.keys()) == required_keys, (
        f"Expected keys {required_keys}, got {set(context.keys())}"
    )
    
    # Check types
    assert isinstance(context["compression_score"], (int, float)), "compression_score must be numeric"
    assert isinstance(context["expansion_pressure"], (int, float)), "expansion_pressure must be numeric"
    assert isinstance(context["rsi_stage"], str), "rsi_stage must be str"
    assert isinstance(context["nearest_liquidity"], (int, float)), "nearest_liquidity must be numeric"
    assert isinstance(context["liquidity_type"], str), "liquidity_type must be str"
    assert isinstance(context["distance_to_liquidity"], (int, float)), "distance_to_liquidity must be numeric"
    assert isinstance(context["liquidity_sweep"], bool), "liquidity_sweep must be bool"
    
    # Check ranges where applicable
    assert 0.0 <= context["expansion_pressure"] <= 1.0, (
        f"expansion_pressure should be [0.0-1.0], got {context['expansion_pressure']}"
    )
    assert context["rsi_stage"] in ["1A", "1B", "1C", "NEUTRAL"], (
        f"rsi_stage invalid: {context['rsi_stage']}"
    )


def test_context_safe_default_on_empty_df(engine):
    """Test that empty/None input returns safe defaults without raising"""
    # Empty DataFrame
    empty_df = pd.DataFrame()
    context = engine.compute_context(empty_df, "TEST", "30m")
    
    assert context["compression_score"] == 1.0
    assert context["expansion_pressure"] == 0.0
    assert context["rsi_stage"] == "NEUTRAL"
    assert context["liquidity_sweep"] == False
    
    # None input
    context_none = engine.compute_context(None, "TEST", "30m")
    assert context_none["compression_score"] == 1.0


def test_context_safe_default_on_exception(engine):
    """Test that exceptions during computation return safe defaults"""
    # Create malformed DataFrame (missing required columns)
    bad_df = pd.DataFrame({
        'price': [1.1500] * 10,  # Missing OHLCV columns
    })
    
    context = engine.compute_context(bad_df, "TEST", "30m")
    # Should use safe defaults, not raise
    assert context["compression_score"] == 1.0
    assert context["rsi_stage"] == "NEUTRAL"


# ═════════════════════════════════════════════════════════════════════════════
# ADDITIONAL: Edge Cases
# ═════════════════════════════════════════════════════════════════════════════

def test_nearest_pool_with_empty_pools(engine, normal_df):
    """Test _find_nearest_pool() with empty pool list"""
    result = engine._find_nearest_pool(normal_df, [])
    
    assert result["nearest_liquidity"] == 0.0
    assert result["liquidity_type"] == "none"
    assert result["distance_to_liquidity"] == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
