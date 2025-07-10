#!/usr/bin/env python3
"""
Test different Stochastic parameters to find the exact match.
"""

import pandas as pd
import numpy as np
import json
import pandas_ta as ta

def main():
    print("=== Testing Different Stochastic Parameters ===\n")
    
    # Load normalized data
    normalized_df = pd.read_csv('/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv')
    
    # Load normalization parameters  
    with open('/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json', 'r') as f:
        norm_params = json.load(f)
    
    # Denormalize OHLC data
    ohlc_columns = ['OPEN', 'HIGH', 'LOW', 'CLOSE']
    denormalized_data = {}
    
    for col in ohlc_columns:
        if col in normalized_df.columns and col in norm_params:
            min_val = norm_params[col]['min']
            max_val = norm_params[col]['max']
            denormalized_data[col] = normalized_df[col] * (max_val - min_val) + min_val
    
    ohlc_df = pd.DataFrame(denormalized_data)
    ohlc_df.columns = ['Open', 'High', 'Low', 'Close']
    
    # Get expected denormalized values for first 10 valid rows
    min_val = norm_params['Stochastic_%D']['min']
    max_val = norm_params['Stochastic_%D']['max']
    reference_norm = normalized_df['Stochastic_%D'].iloc[200:210]
    expected_values = reference_norm * (max_val - min_val) + min_val
    
    print("Expected denormalized values (first 10):")
    print(expected_values.values)
    print(f"Expected range: [{expected_values.min():.6f}, {expected_values.max():.6f}]")
    print()
    
    # Test different Stochastic parameters
    test_params = [
        (14, 3, 3),   # Default
        (5, 3, 3),    # Shorter K period
        (14, 1, 1),   # No smoothing
        (21, 3, 3),   # Longer K period
        (14, 5, 5),   # More smoothing
    ]
    
    for k_period, d_period, smooth_k in test_params:
        print(f"Testing K={k_period}, smooth_k={smooth_k}, D={d_period}:")
        
        try:
            stoch = ta.stoch(ohlc_df['High'], ohlc_df['Low'], ohlc_df['Close'], 
                           k=k_period, d=d_period, smooth_k=smooth_k)
            
            if stoch is not None:
                # Find the %D column
                d_cols = [col for col in stoch.columns if 'STOCHd' in col or 'd' in col.lower()]
                if d_cols:
                    stoch_d = stoch[d_cols[0]]
                    valid_start = stoch_d.first_valid_index()
                    if valid_start is not None:
                        # Get values starting from where reference starts (row 200)
                        calc_values = stoch_d.iloc[200:210]
                        print(f"  Column: {d_cols[0]}")
                        print(f"  Calculated values: {calc_values.values}")
                        print(f"  Range: [{calc_values.min():.6f}, {calc_values.max():.6f}]")
                        
                        # Check if range is close to expected
                        if not calc_values.isna().any():
                            range_diff = abs(calc_values.mean() - expected_values.mean())
                            print(f"  Mean difference from expected: {range_diff:.6f}")
                            if range_diff < 50:  # If reasonably close
                                print("  *** POTENTIAL MATCH ***")
                        print()
                else:
                    print("  No %D column found")
                    print()
            else:
                print("  Calculation failed")
                print()
                
        except Exception as e:
            print(f"  Error: {e}")
            print()

if __name__ == "__main__":
    main()
