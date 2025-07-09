#!/usr/bin/env python3
"""
Feature Generator Module

Handles all feature generation operations including tick calculations
and multi-timeframe feature engineering for the prediction provider.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

class FeatureGenerator:
    """
    Handles all feature generation operations.
    Generates multi-timeframe tick features and other derived features.
    """
    
    def __init__(self):
        """Initialize the feature generator."""
        pass
    
    def generate_all_features(self, hourly_data: pd.DataFrame, data_15m: pd.DataFrame, 
                            data_30m: pd.DataFrame, additional_previous_ticks: int = 0) -> pd.DataFrame:
        """
        Generate all features including ticks and technical indicators.
        
        Args:
            hourly_data: Hourly HLOC and other market data
            data_15m: 15-minute EURUSD data
            data_30m: 30-minute EURUSD data
            additional_previous_ticks: Number of additional previous ticks to include
            
        Returns:
            DataFrame with all generated features
        """
        try:
            # Start with hourly data
            result_data = hourly_data.copy()
            
            # Generate tick features
            tick_features = self._generate_tick_features(hourly_data, data_15m, data_30m, additional_previous_ticks)
            
            # Combine with hourly data
            result_data = result_data.join(tick_features, how='left')
            
            logger.info(f"Generated features shape: {result_data.shape}")
            logger.info(f"Generated features columns: {list(result_data.columns)}")
            
            return result_data
            
        except Exception as e:
            logger.error(f"Error generating features: {e}")
            raise
    
    def _generate_tick_features(self, hourly_data: pd.DataFrame, data_15m: pd.DataFrame, 
                              data_30m: pd.DataFrame, additional_previous_ticks: int = 0) -> pd.DataFrame:
        """
        Generate tick features for each hourly timestamp.
        
        Returns the last 8 + additional_previous_ticks of 15m and 30m prices before each hour.
        """
        tick_features = pd.DataFrame(index=hourly_data.index)
        
        # Define how many ticks to extract (8 base + additional)
        num_ticks = 8 + additional_previous_ticks
        
        # Generate 15-minute tick features
        if not data_15m.empty:
            tick_features_15m = self._extract_ticks(hourly_data.index, data_15m, num_ticks, '15m')
            tick_features = tick_features.join(tick_features_15m, how='left')
        
        # Generate 30-minute tick features  
        if not data_30m.empty:
            tick_features_30m = self._extract_ticks(hourly_data.index, data_30m, num_ticks, '30m')
            tick_features = tick_features.join(tick_features_30m, how='left')
        
        # Forward fill any NaN values
        tick_features = tick_features.ffill()
        
        return tick_features
    
    def _extract_ticks(self, hourly_timestamps: pd.DatetimeIndex, tick_data: pd.DataFrame, 
                      num_ticks: int, timeframe: str) -> pd.DataFrame:
        """
        Extract the last N ticks before each hourly timestamp.
        
        Args:
            hourly_timestamps: The hourly timestamps to extract ticks for
            tick_data: The tick data (15m or 30m)
            num_ticks: Number of ticks to extract
            timeframe: Either '15m' or '30m'
            
        Returns:
            DataFrame with tick columns for each hourly timestamp
        """
        tick_features = pd.DataFrame(index=hourly_timestamps)
        
        # Get the close column name
        close_col = f'CLOSE_{timeframe}'
        
        if close_col not in tick_data.columns:
            logger.warning(f"Column {close_col} not found in tick data")
            return tick_features
        
        # For each hourly timestamp, find the previous N ticks
        for timestamp in hourly_timestamps:
            try:
                # Get ticks before this hour
                before_ticks = tick_data[tick_data.index < timestamp]
                
                if len(before_ticks) >= num_ticks:
                    # Get the last N ticks
                    last_ticks = before_ticks.tail(num_ticks)[close_col].values
                    
                    # Create column names (tick_1 is most recent, tick_N is oldest)
                    for i, tick_value in enumerate(reversed(last_ticks)):
                        col_name = f'tick_{timeframe}_{i+1}'
                        tick_features.loc[timestamp, col_name] = tick_value
                        
                else:
                    # Not enough historical data, use available ticks and pad with first value
                    available_ticks = before_ticks[close_col].values
                    
                    if len(available_ticks) > 0:
                        # Pad with the first available value
                        padded_ticks = np.full(num_ticks, available_ticks[0])
                        padded_ticks[-len(available_ticks):] = available_ticks
                        
                        for i, tick_value in enumerate(reversed(padded_ticks)):
                            col_name = f'tick_{timeframe}_{i+1}'
                            tick_features.loc[timestamp, col_name] = tick_value
                    else:
                        # No historical data available, will be forward filled later
                        logger.warning(f"No tick data available before {timestamp}")
                        
            except Exception as e:
                logger.error(f"Error extracting ticks for {timestamp}: {e}")
                continue
        
        return tick_features
    
    def validate_features(self, data: pd.DataFrame, expected_columns: List[str] = None) -> bool:
        """
        Validate that all expected features are present.
        
        Args:
            data: Generated feature data
            expected_columns: List of expected column names
            
        Returns:
            True if validation passes
        """
        try:
            if expected_columns:
                missing_cols = set(expected_columns) - set(data.columns)
                if missing_cols:
                    logger.error(f"Missing expected columns: {missing_cols}")
                    return False
            
            # Check for NaN values
            nan_counts = data.isnull().sum()
            if nan_counts.any():
                logger.warning(f"NaN values found: {nan_counts[nan_counts > 0].to_dict()}")
            
            logger.info(f"Feature validation passed. Shape: {data.shape}")
            return True
            
        except Exception as e:
            logger.error(f"Error validating features: {e}")
            return False
