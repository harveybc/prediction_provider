#!/usr/bin/env python3
"""
Simplified test of just the Stochastic_%D mapping and normalization
"""

import pandas as pd
import numpy as np
import json
import sys
import os

# Add the plugins_feeder directory to the Python path
sys.path.append('/home/harveybc/Documents/GitHub/prediction_provider/plugins_feeder')

from technical_indicators import TechnicalIndicatorCalculator

def test_stochastic_mapping_only():
    """Test just the Stochastic_%D mapping logic."""
    
    # Load reference data
    normalized_df = pd.read_csv("/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv")
    
    with open("/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json", 'r') as f:
        debug_data = json.load(f)
    
    min_val = debug_data['Stochastic_%D']['min']
    max_val = debug_data['Stochastic_%D']['max']
    
    # Create a dummy raw_values series that simulates what pandas_ta produces
    # Length should match the data, with some NaN values at the beginning
    data_length = len(normalized_df)
    dummy_raw = pd.Series(index=range(data_length), dtype=np.float64)
    
    # Add some NaN values at the beginning (like real stochastic would)
    nan_count = 30  # As observed in debug
    dummy_raw.iloc[:nan_count] = np.nan
    dummy_raw.iloc[nan_count:] = 50.0  # Dummy values
    
    print(f"Created dummy raw values: length={len(dummy_raw)}, NaN count={dummy_raw.isna().sum()}")
    
    # Test the mapping function directly
    calculator = TechnicalIndicatorCalculator()
    mapped_result = calculator._map_to_reference('Stochastic_%D', dummy_raw)
    
    print(f"Mapped result: length={len(mapped_result)}, NaN count={mapped_result.isna().sum()}")
    print(f"Mapped result range (non-NaN): [{mapped_result.dropna().min():.6f}, {mapped_result.dropna().max():.6f}]")
    
    # Check specific values
    for idx in [200, 201, 202]:
        mapped_val = mapped_result.iloc[idx]
        reference_normalized = normalized_df['Stochastic_%D'].iloc[idx]
        reference_denormalized = reference_normalized * (max_val - min_val) + min_val
        
        print(f"\nIndex {idx}:")
        print(f"  Mapped denormalized: {mapped_val:.15f}")
        print(f"  Reference denormalized: {reference_denormalized:.15f}")
        print(f"  Match: {abs(mapped_val - reference_denormalized) < 1e-12}")
    
    # Now test normalization
    print(f"\nTesting normalization:")
    normalized_result = (mapped_result - min_val) / (max_val - min_val)
    
    # Check window offset 200-210
    window_offset = 200
    expected_aligned = normalized_df['Stochastic_%D'].iloc[window_offset:window_offset+10]
    calculated_aligned = normalized_result.iloc[window_offset:window_offset+10]
    
    print(f"Aligned comparison (indices {window_offset}-{window_offset+10}):")
    print(f"Expected: {expected_aligned.tolist()}")
    print(f"Calculated: {calculated_aligned.tolist()}")
    
    differences = np.abs(expected_aligned.values - calculated_aligned.values)
    print(f"Differences: {differences.tolist()}")
    print(f"Max diff: {differences.max():.10f}")
    print(f"Mean diff: {differences.mean():.10f}")
    print(f"Perfect match: {differences.max() < 1e-10}")

if __name__ == "__main__":
    test_stochastic_mapping_only()
