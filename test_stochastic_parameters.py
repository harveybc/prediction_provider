#!/usr/bin/env python3
"""
Test different stochastic parameter combinations to find the one that matches
the reference data in normalized_d4.csv.
"""

import pandas as pd
import numpy as np
import json
import pandas_ta as ta
import sys

def load_test_data():
    """Load the test data for comparison."""
    # Load normalized training data
    d4_path = '/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv'
    normalized_d4 = pd.read_csv(d4_path)
    
    # Load normalization parameters
    debug_path = '/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json'
    with open(debug_path, 'r') as f:
        debug_data = json.load(f)
    
    min_vals = {}
    max_vals = {}
    for feature, values in debug_data.items():
        min_vals[feature] = values['min']
        max_vals[feature] = values['max']
    
    return normalized_d4, min_vals, max_vals

def denormalize_ohlc(normalized_d4, min_vals, max_vals):
    """Denormalize OHLC columns."""
    denormalized_data = pd.DataFrame()
    
    for col in ['OPEN', 'HIGH', 'LOW', 'CLOSE']:
        if col in normalized_d4.columns:
            min_val = min_vals[col]
            max_val = max_vals[col]
            denormalized_data[col] = normalized_d4[col] * (max_val - min_val) + min_val
            
    return denormalized_data

def test_stochastic_parameters():
    """Test various stochastic parameter combinations."""
    print("=== Testing Stochastic Parameter Combinations ===\n")
    
    # Load and prepare data
    normalized_d4, min_vals, max_vals = load_test_data()
    ohlc_data = denormalize_ohlc(normalized_d4, min_vals, max_vals)
    
    # Get reference values
    ref_normalized = normalized_d4['Stochastic_%D'].copy()
    min_val = min_vals['Stochastic_%D']
    max_val = max_vals['Stochastic_%D']
    ref_denormalized = ref_normalized * (max_val - min_val) + min_val
    
    print(f"Reference Stochastic_%D range: [{ref_denormalized.min():.6f}, {ref_denormalized.max():.6f}]")
    
    # Test different parameter combinations
    parameter_combinations = [
        # (k_period, d_period, smooth_k) - standard is (14, 3, 3)
        (14, 3, 3),    # Default/standard
        (5, 3, 3),     # Faster
        (21, 3, 3),    # Slower
        (14, 1, 1),    # No smoothing
        (14, 5, 5),    # More smoothing
        (10, 3, 3),    # Medium period
        (9, 3, 3),     # Common short period
        (14, 3, 1),    # Different smoothing
        (14, 1, 3),    # Different smoothing
        (7, 3, 3),     # Short period
        (28, 3, 3),    # Long period
    ]
    
    best_match = None
    best_max_diff = float('inf')
    
    for k_period, d_period, smooth_k in parameter_combinations:
        print(f"\nTesting parameters: k_period={k_period}, d_period={d_period}, smooth_k={smooth_k}")
        
        try:
            # Calculate stochastic with specific parameters
            stoch = ta.stoch(
                high=ohlc_data['HIGH'], 
                low=ohlc_data['LOW'], 
                close=ohlc_data['CLOSE'],
                k=k_period,
                d=d_period,
                smooth_k=smooth_k
            )
            
            print(f"  Columns returned: {list(stoch.columns) if stoch is not None else 'None'}")
            
            if stoch is not None and len(stoch.columns) > 0:
                # Look for %D column (could be named differently based on parameters)
                d_column = None
                for col in stoch.columns:
                    if 'd' in col.lower() and 'stoch' in col.lower():
                        d_column = col
                        break
                
                if d_column is not None:
                    our_stoch_d = stoch[d_column].dropna()
                    print(f"  Found %D column: {d_column}")
                    print(f"  Our range: [{our_stoch_d.min():.6f}, {our_stoch_d.max():.6f}]")
                    
                    # Align data for comparison (first 1000 valid values)
                    if len(our_stoch_d) >= 1000:
                        first_valid_idx = stoch[d_column].first_valid_index()
                        if first_valid_idx is not None:
                            offset = stoch.index.get_loc(first_valid_idx)
                            
                            our_values = our_stoch_d.head(1000).values
                            ref_values = ref_denormalized.iloc[offset:offset + len(our_values)].values
                            
                            min_length = min(len(our_values), len(ref_values))
                            our_values = our_values[:min_length]
                            ref_values = ref_values[:min_length]
                            
                            if len(our_values) > 0:
                                max_diff = np.abs(our_values - ref_values).max()
                                mean_diff = np.abs(our_values - ref_values).mean()
                                
                                print(f"  Max difference: {max_diff:.6f}")
                                print(f"  Mean difference: {mean_diff:.6f}")
                                
                                if max_diff < best_max_diff:
                                    best_max_diff = max_diff
                                    best_match = (k_period, d_period, smooth_k, max_diff, mean_diff)
                                
                                # Check if this is a very close match
                                if max_diff < 0.01:
                                    print(f"  🎉 EXCELLENT MATCH FOUND!")
                                    print(f"  Parameters: k_period={k_period}, d_period={d_period}, smooth_k={smooth_k}")
                                    return k_period, d_period, smooth_k
                                elif max_diff < 0.1:
                                    print(f"  ✅ Good match!")
                else:
                    print(f"  No %D column found in: {list(stoch.columns)}")
            else:
                print(f"  No stochastic data returned")
                
        except Exception as e:
            print(f"  Error with parameters ({k_period}, {d_period}, {smooth_k}): {e}")
    
    if best_match:
        print(f"\n=== BEST MATCH ===")
        k, d, s, max_diff, mean_diff = best_match
        print(f"Parameters: k_period={k}, d_period={d}, smooth_k={s}")
        print(f"Max difference: {max_diff:.6f}")
        print(f"Mean difference: {mean_diff:.6f}")
        return k, d, s
    else:
        print(f"\nNo good matches found with standard parameter variations.")
        return None, None, None

if __name__ == '__main__':
    test_stochastic_parameters()
