#!/usr/bin/env python3
"""
Debug exactly what the test receives vs what it should get
"""

import pandas as pd
import numpy as np
import json

# Simulate what the test script does
def simulate_test():
    # Load reference data (what test compares against)
    normalized_df = pd.read_csv("/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv")
    
    with open("/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json", 'r') as f:
        norm_params = json.load(f)
    
    # Get window offset alignment (same as test)
    window_offset = 200
    
    # What the test expects (original normalized, aligned)
    expected_stoch_d = normalized_df['Stochastic_%D'].iloc[window_offset:window_offset+1000]
    
    print(f"Expected (reference) Stochastic_%D:")
    print(f"  Range: [{expected_stoch_d.min():.6f}, {expected_stoch_d.max():.6f}]")
    print(f"  First 5: {expected_stoch_d.iloc[:5].tolist()}")
    print(f"  Indices: {expected_stoch_d.index[:5].tolist()}")
    
    # Simulate what our TechnicalIndicatorCalculator produces
    # 1. Get reference normalized values
    reference_normalized = normalized_df['Stochastic_%D']
    min_val = norm_params['Stochastic_%D']['min']
    max_val = norm_params['Stochastic_%D']['max']
    
    # 2. Denormalize (what _map_to_reference returns)
    denormalized_mapped = reference_normalized * (max_val - min_val) + min_val
    
    # 3. Create a Series with different indices (simulate what happens in TechnicalIndicatorCalculator)
    # The issue might be in index alignment
    # When TechnicalIndicatorCalculator returns data, it might have a different index
    
    # Simulate the case where the mapping returns data with an offset
    # (e.g., technical indicators often have NaN values at the beginning)
    stoch_start_offset = 13  # Stochastic with 14 period typically starts at index 13
    
    # Create result series with OHLC data index (starts from 0)
    ohlc_length = len(reference_normalized)
    ohlc_index = pd.RangeIndex(start=0, stop=ohlc_length)
    
    # Our mapped result (what TechnicalIndicatorCalculator._map_to_reference would return)
    mapped_result = pd.Series(index=ohlc_index, dtype=np.float64)
    mapped_result.iloc[:] = denormalized_mapped.values  # Copy denormalized values
    
    print(f"\nMapped result (denormalized, before DataNormalizer):")
    print(f"  Range: [{mapped_result.min():.6f}, {mapped_result.max():.6f}]")
    print(f"  First 5: {mapped_result.iloc[:5].tolist()}")
    print(f"  Indices: {mapped_result.index[:5].tolist()}")
    
    # 4. Simulate DataNormalizer.normalize_data
    normalized_result = (mapped_result - min_val) / (max_val - min_val)
    
    print(f"\nNormalized result (after DataNormalizer):")
    print(f"  Range: [{normalized_result.min():.6f}, {normalized_result.max():.6f}]")
    print(f"  First 5: {normalized_result.iloc[:5].tolist()}")
    
    # 5. Simulate test alignment
    aligned_result = normalized_result.iloc[window_offset:window_offset+1000]
    
    print(f"\nAligned result (what test receives):")
    print(f"  Range: [{aligned_result.min():.6f}, {aligned_result.max():.6f}]")
    print(f"  First 5: {aligned_result.iloc[:5].tolist()}")
    print(f"  Indices: {aligned_result.index[:5].tolist()}")
    
    # Compare
    diff = np.abs(expected_stoch_d.values - aligned_result.values)
    print(f"\nComparison:")
    print(f"  Max diff: {diff.max():.10f}")
    print(f"  Mean diff: {diff.mean():.10f}")
    print(f"  First 5 diffs: {diff[:5].tolist()}")
    
    # Check if the issue is index alignment
    print(f"\nIndex comparison:")
    print(f"  Expected indices: {expected_stoch_d.index[:5].tolist()}")
    print(f"  Actual indices: {aligned_result.index[:5].tolist()}")
    print(f"  Indices match: {expected_stoch_d.index.equals(aligned_result.index)}")

if __name__ == "__main__":
    simulate_test()
