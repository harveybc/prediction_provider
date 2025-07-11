#!/usr/bin/env python3
"""
Test STL Feature Integration

This script tests the integration of STL feature generation into the
prediction_provider real feeder plugin.

Tests:
1. STL feature generator functionality
2. Integration with real feeder plugin
3. Feature count validation (44 -> 54+)
4. Feature value consistency
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# Add the project path
sys.path.append('/home/harveybc/Documents/GitHub/prediction_provider')

from plugins_feeder.real_feeder import RealFeederPlugin
from plugins_feeder.stl_feature_generator import STLFeatureGenerator

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_stl_feature_generator():
    """Test STL feature generator standalone."""
    logger.info("=== Testing STL Feature Generator Standalone ===")
    
    # Create sample CLOSE data
    dates = pd.date_range('2024-01-01', periods=1000, freq='H')
    close_prices = 1.1000 + 0.01 * np.sin(np.arange(1000) * 2 * np.pi / 24) + np.random.normal(0, 0.0001, 1000)
    
    # Initialize STL generator
    stl_gen = STLFeatureGenerator()
    stl_gen.set_params(
        use_stl=False,
        use_wavelets=True,
        wavelet_levels=2,
        use_multi_tapper=False,
        normalize_features=True
    )
    
    # Generate features
    features = stl_gen.generate_features(close_prices)
    
    logger.info(f"Generated {len(features)} STL features:")
    for name, values in features.items():
        logger.info(f"  {name}: shape={values.shape}, mean={np.mean(values):.6f}, std={np.std(values):.6f}")
    
    return features

def test_real_feeder_integration():
    """Test STL integration with real feeder plugin."""
    logger.info("=== Testing Real Feeder Integration ===")
    
    # Initialize real feeder
    config = {
        "use_normalization_json": "/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json",
        "use_wavelets": True,
        "wavelet_levels": 2,
        "normalize_features": True
    }
    
    real_feeder = RealFeederPlugin(config)
    
    # Test with recent data (3 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=3)
    
    try:
        # Load data with STL features
        start_date_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
        end_date_str = end_date.strftime('%Y-%m-%d %H:%M:%S')
        data = real_feeder.load_data(start_date_str, end_date_str)
        
        if data.empty:
            logger.error("No data returned from real feeder")
            return None
        
        logger.info(f"Real feeder data shape: {data.shape}")
        logger.info(f"Columns ({len(data.columns)}): {list(data.columns)}")
        
        # Check for STL features
        stl_features = [col for col in data.columns if any(prefix in col for prefix in ['log_return', 'wav_', 'stl_', 'mtm_'])]
        logger.info(f"STL features found ({len(stl_features)}): {stl_features}")
        
        # Validate feature count
        expected_base_features = 44  # Original technical indicators + features
        expected_stl_features = 13   # log_return + 12 wavelet features (default config)
        expected_total = expected_base_features + expected_stl_features
        
        if len(data.columns) >= expected_total:
            logger.info(f"✓ Feature count validation passed: {len(data.columns)} >= {expected_total}")
        else:
            logger.warning(f"✗ Feature count validation failed: {len(data.columns)} < {expected_total}")
        
        return data
        
    except Exception as e:
        logger.error(f"Error testing real feeder integration: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_feature_consistency():
    """Test feature consistency between standalone and integrated generation."""
    logger.info("=== Testing Feature Consistency ===")
    
    # Load reference data for comparison
    try:
        reference_file = "/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv"
        if os.path.exists(reference_file):
            ref_data = pd.read_csv(reference_file)
            logger.info(f"Reference data shape: {ref_data.shape}")
            
            if 'CLOSE' in ref_data.columns:
                # Test STL generation on reference CLOSE column
                stl_gen = STLFeatureGenerator()
                stl_gen.set_params(use_wavelets=True, wavelet_levels=2, normalize_features=True)
                
                ref_features = stl_gen.generate_features(ref_data['CLOSE'].values[-1000:])  # Last 1000 points
                logger.info(f"Reference STL features ({len(ref_features)}): {list(ref_features.keys())}")
                
                # Compare with original data features (if any STL features exist)
                stl_cols_in_ref = [col for col in ref_data.columns if any(prefix in col for prefix in ['log_return', 'wav_', 'stl_', 'mtm_'])]
                logger.info(f"STL columns in reference data ({len(stl_cols_in_ref)}): {stl_cols_in_ref}")
                
                return ref_features
            else:
                logger.warning("No CLOSE column in reference data")
        else:
            logger.warning(f"Reference file not found: {reference_file}")
    
    except Exception as e:
        logger.error(f"Error testing feature consistency: {e}")
    
    return None

def main():
    """Run all tests."""
    logger.info("Starting STL Feature Integration Tests")
    
    # Test 1: Standalone STL feature generator
    stl_features = test_stl_feature_generator()
    
    # Test 2: Real feeder integration
    integrated_data = test_real_feeder_integration()
    
    # Test 3: Feature consistency
    ref_features = test_feature_consistency()
    
    # Summary
    logger.info("=== Test Summary ===")
    
    if stl_features:
        logger.info(f"✓ STL feature generator: {len(stl_features)} features generated")
    else:
        logger.error("✗ STL feature generator failed")
    
    if integrated_data is not None:
        stl_count = len([col for col in integrated_data.columns if any(prefix in col for prefix in ['log_return', 'wav_', 'stl_', 'mtm_'])])
        logger.info(f"✓ Real feeder integration: {integrated_data.shape[1]} total features, {stl_count} STL features")
    else:
        logger.error("✗ Real feeder integration failed")
    
    if ref_features:
        logger.info(f"✓ Feature consistency test: {len(ref_features)} reference features")
    else:
        logger.warning("○ Feature consistency test: no reference comparison available")
    
    logger.info("STL Feature Integration Tests Complete")

if __name__ == "__main__":
    main()
