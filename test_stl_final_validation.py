#!/usr/bin/env python3
"""
Final validation test for STL integration.

This test validates that the STL integration produces exactly 54 features
matching the phase_3 predictor model requirements.
"""

import pandas as pd
import numpy as np
import pytest
from plugins_feeder.real_feeder import RealFeederPlugin
from datetime import datetime, timedelta


def test_stl_integration_feature_count():
    """Test that STL integration produces exactly 54 features."""
    
    # Initialize the real feeder with STL enabled
    config = {
        'use_stl': True,
        'use_wavelets': True,
        'use_multi_tapper': True,
        'additional_previous_ticks': 0
    }
    
    real_feeder = RealFeederPlugin(config)
    
    # Load sufficient data for STL decomposition
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5)
    
    try:
        data = real_feeder.load_data(
            start_date.strftime('%Y-%m-%d %H:%M:%S'), 
            end_date.strftime('%Y-%m-%d %H:%M:%S')
        )
        
        # Validate data is not empty
        assert data is not None, "Data should not be None"
        assert not data.empty, "Data should not be empty"
        
        # Validate feature count
        assert len(data.columns) == 54, f"Expected 54 features, got {len(data.columns)}"
        
        # Validate STL features are present
        stl_features = [col for col in data.columns if any(prefix in col for prefix in ['log_return', 'wav_', 'stl_', 'mtm_'])]
        assert len(stl_features) == 11, f"Expected 11 STL features, got {len(stl_features)}"
        
        # Validate specific STL features
        expected_stl_features = [
            'log_return',
            'stl_trend', 'stl_seasonal', 'stl_resid',
            'wav_detail_L1', 'wav_detail_L2', 'wav_approx_L2',
            'mtm_mtm_band_0_power', 'mtm_mtm_band_1_power', 'mtm_mtm_band_2_power', 'mtm_mtm_band_3_power'
        ]
        
        for feature in expected_stl_features:
            assert feature in data.columns, f"Expected STL feature '{feature}' not found"
        
        # Validate OHLC handling (OPEN, HIGH, LOW should be present, CLOSE should be absent)
        assert 'OPEN' in data.columns, "OPEN should be preserved"
        assert 'HIGH' in data.columns, "HIGH should be preserved"  
        assert 'LOW' in data.columns, "LOW should be preserved"
        assert 'CLOSE' not in data.columns, "CLOSE should be replaced by log_return"
        
        # Validate tick features
        tick_features = [col for col in data.columns if 'tick' in col]
        assert len(tick_features) == 16, f"Expected 16 tick features, got {len(tick_features)}"
        
        # Validate technical indicators
        tech_indicators = ['RSI', 'MACD', 'MACD_Signal', 'MACD_Histogram', 'EMA', 
                          'Stochastic_%K', 'Stochastic_%D', 'ADX', 'DI+', 'DI-', 
                          'ATR', 'CCI', 'WilliamsR', 'Momentum', 'ROC']
        for indicator in tech_indicators:
            assert indicator in data.columns, f"Expected technical indicator '{indicator}' not found"
        
        print(f"✅ SUCCESS: STL integration produces exactly {len(data.columns)} features")
        print(f"✅ STL features: {len(stl_features)}/11")
        print(f"✅ Tick features: {len(tick_features)}/16")
        print(f"✅ Technical indicators: {len(tech_indicators)}/15")
        
        return True
        
    except Exception as e:
        pytest.fail(f"STL integration test failed: {e}")


def test_stl_feature_data_quality():
    """Test that STL features contain valid data."""
    
    config = {
        'use_stl': True,
        'use_wavelets': True,
        'use_multi_tapper': True,
        'additional_previous_ticks': 0
    }
    
    real_feeder = RealFeederPlugin(config)
    
    # Load sufficient data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=3)
    
    try:
        data = real_feeder.load_data(
            start_date.strftime('%Y-%m-%d %H:%M:%S'), 
            end_date.strftime('%Y-%m-%d %H:%M:%S')
        )
        
        # Check that STL features have valid data (not all NaN or constant)
        stl_features = [col for col in data.columns if any(prefix in col for prefix in ['log_return', 'wav_', 'stl_', 'mtm_'])]
        
        for feature in stl_features:
            feature_data = data[feature]
            
            # Check for non-NaN values
            assert not feature_data.isna().all(), f"STL feature '{feature}' is all NaN"
            
            # Check for finite values
            assert np.isfinite(feature_data).any(), f"STL feature '{feature}' has no finite values"
        
        print(f"✅ STL feature data quality validation passed")
        return True
        
    except Exception as e:
        pytest.fail(f"STL feature data quality test failed: {e}")


if __name__ == "__main__":
    print("🧪 Running STL Integration Final Validation Tests")
    print("=" * 60)
    
    try:
        test_stl_integration_feature_count()
        print()
        test_stl_feature_data_quality()
        print()
        print("🎉 All STL integration tests PASSED!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        exit(1)
