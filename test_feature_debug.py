#!/usr/bin/env python3
"""
Simple test to debug feature generation issues
"""

import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# Add the project path
sys.path.append('/home/harveybc/Documents/GitHub/prediction_provider')

from plugins_feeder.real_feeder import RealFeederPlugin

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_feature_generation_detailed():
    """Test feature generation step by step"""
    print("=== Detailed Feature Generation Test ===")
    
    # Create minimal config
    config = {
        "use_normalization_json": "/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json",
        "use_wavelets": True,
        "wavelet_levels": 2,
        "normalize_features": True
    }
    
    real_feeder = RealFeederPlugin(config)
    
    # Use minimal time range
    end_date = datetime.now()
    start_date = end_date - timedelta(hours=6)  # Just 6 hours
    
    try:
        print(f"Testing with date range: {start_date} to {end_date}")
        
        # Initialize components first
        real_feeder._initialize_components()
        
        # Step 1: Test data fetching
        print("\n--- Step 1: Data Fetching ---")
        hourly_data, data_15m, data_30m = real_feeder.data_fetcher.fetch_all_timeframes(start_date, end_date)
        
        print(f"Hourly data shape: {hourly_data.shape}")
        print(f"Hourly data columns: {list(hourly_data.columns)}")
        
        print(f"15m data shape: {data_15m.shape}")
        print(f"30m data shape: {data_30m.shape}")
        
        # Step 2: Test feature generation
        print("\n--- Step 2: Feature Generation ---")
        feature_data = real_feeder.feature_generator.generate_all_features(
            hourly_data, data_15m, data_30m, 0  # Use 0 additional ticks for standard 8 tick features
        )
        
        print(f"Feature data shape: {feature_data.shape}")
        print(f"Feature data columns ({len(feature_data.columns)}):")
        for i, col in enumerate(feature_data.columns):
            print(f"  {i+1:2d}. {col}")
        
        # Check specific features
        sp500_present = 'S&P500_Close' in feature_data.columns
        vix_present = 'vix_close' in feature_data.columns
        
        tick_15m_features = [col for col in feature_data.columns if 'CLOSE_15m_tick_' in col]
        tick_30m_features = [col for col in feature_data.columns if 'CLOSE_30m_tick_' in col]
        
        print(f"\nFeature Analysis:")
        print(f"  S&P500_Close present: {sp500_present}")
        print(f"  vix_close present: {vix_present}")
        print(f"  15m tick features: {len(tick_15m_features)}")
        print(f"  30m tick features: {len(tick_30m_features)}")
        
        if len(tick_15m_features) > 0:
            print(f"  15m tick feature examples: {tick_15m_features[:3]}")
        if len(tick_30m_features) > 0:
            print(f"  30m tick feature examples: {tick_30m_features[:3]}")
        
        return feature_data
        
    except Exception as e:
        print(f"Error in detailed test: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_feature_generation_detailed()
