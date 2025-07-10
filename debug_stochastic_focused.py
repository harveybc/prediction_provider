#!/usr/bin/env python3
"""
Focused test to debug the Stochastic_%D alignment issue
"""

import pandas as pd
import numpy as np
import json
import sys

sys.path.append('/home/harveybc/Documents/GitHub/prediction_provider/plugins_feeder')
from technical_indicators import TechnicalIndicatorCalculator

def debug_stochastic_alignment():
    """Debug the exact alignment issue with Stochastic_%D"""
    print("=== Debugging Stochastic_%D Alignment ===\n")
    
    # Load data
    d4_path = '/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv'
    normalized_d4 = pd.read_csv(d4_path)
    
    debug_path = '/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json'
    with open(debug_path, 'r') as f:
        debug_data = json.load(f)
    
    # Denormalize OHLC
    ohlc_data = pd.DataFrame()
    for col in ['OPEN', 'HIGH', 'LOW', 'CLOSE']:
        min_val = debug_data[col]['min']
        max_val = debug_data[col]['max']
        ohlc_data[col] = normalized_d4[col] * (max_val - min_val) + min_val
    
    # Calculate indicators
    calculator = TechnicalIndicatorCalculator()
    indicators = calculator.calculate_all_indicators(ohlc_data)
    
    # Get our Stochastic_%D
    our_stoch_d = indicators['Stochastic_%D']
    
    # Get normalized reference Stochastic_%D
    ref_stoch_d_norm = normalized_d4['Stochastic_%D']
    
    # Renormalize our calculated values
    stoch_d_min = debug_data['Stochastic_%D']['min']
    stoch_d_max = debug_data['Stochastic_%D']['max']
    
    # Our values are already denormalized (from direct mapping), so we need to normalize them
    our_stoch_d_norm = (our_stoch_d - stoch_d_min) / (stoch_d_max - stoch_d_min)
    
    print(f"Reference normalized Stochastic_%D shape: {ref_stoch_d_norm.shape}")
    print(f"Our normalized Stochastic_%D shape: {our_stoch_d_norm.shape}")
    print(f"Our Stochastic_%D NaN count: {our_stoch_d_norm.isna().sum()}")
    print(f"Reference Stochastic_%D NaN count: {ref_stoch_d_norm.isna().sum()}")
    
    # Check alignment at different offsets
    window_offset = 200
    print(f"\nUsing window offset: {window_offset}")
    
    # Apply the same alignment as the test script
    ref_aligned = ref_stoch_d_norm.iloc[window_offset:window_offset + 1000]
    our_aligned = our_stoch_d_norm.iloc[window_offset:window_offset + 1000]
    
    print(f"Reference aligned shape: {ref_aligned.shape}")
    print(f"Our aligned shape: {our_aligned.shape}")
    
    # Check for exact matches
    print(f"\nFirst 10 reference values: {ref_aligned.head(10).tolist()}")
    print(f"First 10 our values: {our_aligned.head(10).tolist()}")
    
    # Calculate differences
    diff = np.abs(ref_aligned.values - our_aligned.values)
    max_diff = np.max(diff)
    mean_diff = np.mean(diff)
    
    print(f"\nMax difference: {max_diff:.8f}")
    print(f"Mean difference: {mean_diff:.8f}")
    
    # Find where the biggest differences occur
    max_diff_idx = np.argmax(diff)
    print(f"\nBiggest difference at index {max_diff_idx}:")
    print(f"  Reference: {ref_aligned.iloc[max_diff_idx]:.8f}")
    print(f"  Our value: {our_aligned.iloc[max_diff_idx]:.8f}")
    print(f"  Difference: {diff[max_diff_idx]:.8f}")
    
    # Check if our values are actually identical to reference but at wrong offset
    print(f"\n=== Testing Different Offsets ===")
    for test_offset in range(0, 50, 5):
        if window_offset + test_offset + 100 < len(our_stoch_d_norm):
            test_ref = ref_stoch_d_norm.iloc[window_offset:window_offset + 100]
            test_our = our_stoch_d_norm.iloc[window_offset + test_offset:window_offset + test_offset + 100]
            
            test_diff = np.abs(test_ref.values - test_our.values)
            test_max_diff = np.max(test_diff)
            
            print(f"Offset {test_offset:2d}: Max diff = {test_max_diff:.8f}")
            
            if test_max_diff < 1e-6:
                print(f"  🎉 PERFECT MATCH FOUND AT OFFSET {test_offset}!")
                break

if __name__ == '__main__':
    debug_stochastic_alignment()
