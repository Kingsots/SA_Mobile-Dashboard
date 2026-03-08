"""
Volume Filter
Detects volume spikes for trade confirmation.
"""

import pandas as pd
from typing import Tuple
from core.indicators import TechnicalIndicators
from core.config import Config


class VolumeFilter:
    """
    Volume spike detection matching Pine Script logic.
    
    Pine Script equivalent:
    avgVol = ta.sma(volume, volPeriod)
    volume > avgVol * volMult
    """
    
    @staticmethod
    def check_volume_spike(df: pd.DataFrame, 
                          period: int = None, 
                          multiplier: float = None) -> Tuple[bool, dict]:
        """
        Check if current volume is above average threshold
        
        Pine Script equivalent:
        volume > avgVol * volMult
        
        Args:
            df: DataFrame with 'volume' column
            period: SMA period (default: from config)
            multiplier: Volume multiplier threshold (default: from config)
        
        Returns:
            Tuple of (has_spike: bool, volume_data: dict)
        """
        if period is None:
            period = Config.VOLUME_PERIOD
        
        if multiplier is None:
            multiplier = Config.VOLUME_MULTIPLIER
        
        if df is None or df.empty or len(df) < period:
            return False, {
                'current_volume': 0,
                'average_volume': 0,
                'multiplier': multiplier,
                'threshold': 0,
                'spike': False,
                'ratio': 0.0
            }
        
        try:
            # Calculate volume SMA
            avg_volume = TechnicalIndicators.calculate_sma(df['volume'], period)
            current_volume = float(df['volume'].iloc[-1])
            
            # Calculate threshold
            threshold = avg_volume * multiplier
            
            # Check if current volume exceeds threshold
            has_spike = current_volume > threshold
            
            # Calculate ratio
            ratio = (current_volume / avg_volume) if avg_volume > 0 else 0.0
            
            volume_data = {
                'current_volume': current_volume,
                'average_volume': avg_volume,
                'multiplier': multiplier,
                'threshold': threshold,
                'spike': has_spike,
                'ratio': round(ratio, 2)
            }
            
            return has_spike, volume_data
            
        except Exception as e:
            print(f"Volume filter error: {e}")
            return False, {
                'current_volume': 0,
                'average_volume': 0,
                'multiplier': multiplier,
                'threshold': 0,
                'spike': False,
                'ratio': 0.0
            }
    
    @staticmethod
    def get_volume_strength(ratio: float) -> str:
        """
        Classify volume strength based on ratio
        
        Args:
            ratio: Current volume / Average volume
        
        Returns:
            Strength classification
        """
        if ratio >= 2.0:
            return "VERY HIGH"
        elif ratio >= 1.5:
            return "HIGH"
        elif ratio >= 1.2:
            return "MODERATE"
        elif ratio >= 1.0:
            return "NORMAL"
        else:
            return "LOW"
    
    @staticmethod
    def format_volume_info(volume_data: dict) -> str:
        """
        Format volume information for display
        
        Args:
            volume_data: Volume analysis dictionary
        
        Returns:
            Formatted string
        """
        strength = VolumeFilter.get_volume_strength(volume_data['ratio'])
        spike_icon = "✅" if volume_data['spike'] else "❌"
        
        return (
            f"{spike_icon} Volume: {volume_data['current_volume']:,.0f} "
            f"(Avg: {volume_data['average_volume']:,.0f} | "
            f"Ratio: {volume_data['ratio']:.2f}x | "
            f"Strength: {strength})"
        )
