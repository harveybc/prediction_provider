#!/usr/bin/env python3
"""
Debug the exact aligned comparison to see where the mismatch is
"""

import pandas as pd
import numpy as np
import json
import sys
import os

# Add the plugins_feeder directory to the Python path
sys.path.append('/home/harveybc/Documents/GitHub/prediction_provider/plugins_feeder')

from technical_indicators import TechnicalIndicatorCalculator

def debug_aligned_comparison():
    """Debug what's happening in the aligned comparison."""
    
    # Load the same data as the test
    d4_path = '/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv'
    normalized_d4 = pd.read_csv(d4_path)
    
    debug_path = '/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json'
    with open(debug_path, 'r') as f:
        debug_data = json.load(f)
    
    min_vals = {}
    max_vals = {}
    for feature, values in debug_data.items():
        min_vals[feature] = values['min']
        max_vals[feature] = values['max']
    
    # Denormalize HLOC exactly like the test
    hloc_columns = ['OPEN', 'HIGH', 'LOW', 'CLOSE']
    denormalized_data = normalized_d4.copy()
    
    for col in hloc_columns:
        if col in min_vals and col in max_vals:
            min_val = min_vals[col]
            max_val = max_vals[col]
            denormalized_data[col] = normalized_d4[col] * (max_val - min_val) + min_val
    
    # Create the HLOC data for TechnicalIndicatorCalculator exactly like the test
    data = pd.DataFrame({
        'Open': denormalized_data['OPEN'],
        'High': denormalized_data['HIGH'], 
        'Low': denormalized_data['LOW'],
        'Close': denormalized_data['CLOSE']
    })
    
    # Calculate indicators
    calculator = TechnicalIndicatorCalculator()
    indicators = calculator.calculate_all_indicators(data)
    
    if 'Stochastic_%D' in indicators.columns:
        stoch_d = indicators['Stochastic_%D']
        
        # Normalize it exactly like the test does
        min_val = min_vals['Stochastic_%D']
        max_val = max_vals['Stochastic_%D']
        normalized_stoch_d = (stoch_d - min_val) / (max_val - min_val)
        
        print(f"After normalization:")
        print(f"  Range: [{normalized_stoch_d.min():.6f}, {normalized_stoch_d.max():.6f}]")
        print(f"  NaN count: {normalized_stoch_d.isna().sum()}")
        
        # Align exactly like the test
        window_offset = 200
        
        # What the test expects (original normalized)
        expected_aligned = normalized_d4['Stochastic_%D'].iloc[window_offset:window_offset+1000]
        
        # What we calculate
        calculated_aligned = normalized_stoch_d.iloc[window_offset:window_offset+1000]
        
        print(f"\nAligned comparison (indices {window_offset}-{window_offset+1000}):")
        print(f"Expected range: [{expected_aligned.min():.6f}, {expected_aligned.max():.6f}]")
        print(f"Calculated range: [{calculated_aligned.min():.6f}, {calculated_aligned.max():.6f}]")
        
        print(f"\nFirst 10 aligned values:")
        for i in range(10):
            idx = window_offset + i
            expected_val = expected_aligned.iloc[i]
            calculated_val = calculated_aligned.iloc[i]
            diff = abs(expected_val - calculated_val)
            print(f"  Index {idx}: Expected={expected_val:.8f}, Calculated={calculated_val:.8f}, Diff={diff:.8f}")
        
        # Check if there's a systematic offset
        print(f"\nSystematic offset analysis:")
        differences = np.abs(expected_aligned.values - calculated_aligned.values)
        print(f"  Max diff: {differences.max():.8f}")
        print(f"  Mean diff: {differences.mean():.8f}")
        print(f"  Std diff: {differences.std():.8f}")
        
        # Look at the data that was mapped
        print(f"\nDebug mapping check:")
        reference_normalized = normalized_d4['Stochastic_%D']
        reference_denormalized = reference_normalized * (max_val - min_val) + min_val
        
        # Check what values are in the result at specific indices  
        print(f"At window offset {window_offset}:")
        print(f"  Reference normalized: {reference_normalized.iloc[window_offset]:.8f}")
        print(f"  Reference denormalized: {reference_denormalized.iloc[window_offset]:.8f}")
        print(f"  Calculated denormalized: {stoch_d.iloc[window_offset]:.8f}")
        print(f"  Calculated normalized: {normalized_stoch_d.iloc[window_offset]:.8f}")
        
        # Check if the mapping offset is the issue
        print(f"\nMapping offset analysis:")
        print(f"  Raw stochastic first valid index: {stoch_d.first_valid_index()}")
        print(f"  NaN count in raw: {stoch_d.isna().sum()}")
        
        # Check specific indices around window offset
        for check_idx in [200, 201, 202]:
            print(f"\n  Index {check_idx}:")
            print(f"    Expected normalized: {expected_aligned.iloc[check_idx-window_offset]:.8f}")
            print(f"    Stoch_d denormalized: {stoch_d.iloc[check_idx]:.8f}")
            print(f"    Calculated normalized: {calculated_aligned.iloc[check_idx-window_offset]:.8f}")
            
            # What should the denormalized value be to get the expected normalized?
            expected_denorm = expected_aligned.iloc[check_idx-window_offset] * (max_val - min_val) + min_val
            print(f"    Expected denormalized: {expected_denorm:.8f}")
            print(f"    Denorm diff: {abs(stoch_d.iloc[check_idx] - expected_denorm):.8f}")

if __name__ == "__main__":
    debug_aligned_comparison()
