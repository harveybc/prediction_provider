#!/usr/bin/env python3
"""
Exact comparison with feature-eng logic to identify the root cause of differences.
"""

import pandas as pd
import pandas_ta as ta
import numpy as np
import json

def main():
    print("=== Exact Feature-Eng Comparison ===")
    
    # Load data like our test does
    d4_path = '/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv'
    normalized_d4 = pd.read_csv(d4_path)
    
    debug_path = '/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json'
    with open(debug_path, 'r') as f:
        debug_data = json.load(f)
    
    min_vals = {k: v['min'] for k, v in debug_data.items()}
    max_vals = {k: v['max'] for k, v in debug_data.items()}
    
    # Use the same test range as our validation
    test_range = slice(200, 1200)
    ohlc_cols = ['OPEN', 'HIGH', 'LOW', 'CLOSE']
    
    # Denormalize exactly like our test
    denormalized = pd.DataFrame()
    for col in ohlc_cols:
        min_val = min_vals[col] 
        max_val = max_vals[col]
        denormalized[col] = normalized_d4[col].iloc[test_range] * (max_val - min_val) + min_val
    
    # Rename for pandas_ta (exactly like feature-eng after adjust_ohlc)
    data = denormalized.copy()
    data.columns = ['Open', 'High', 'Low', 'Close']
    
    print(f"Data shape: {data.shape}")
    print(f"Close sample: {data['Close'].iloc[50:55].values}")
    
    # Test each failing indicator with EXACT feature-eng logic
    failing_indicators = ['MACD', 'MACD_Signal', 'Stochastic_%D', 'ADX']
    
    for indicator_name in failing_indicators:
        print(f"\n=== {indicator_name} ===")
        
        if indicator_name in ['MACD', 'MACD_Signal']:
            # EXACT feature-eng logic
            macd = ta.macd(data['Close'])  # Default fast, slow, signal periods
            if macd is not None:
                print(f"MACD columns: {macd.columns.tolist()}")
                
                if indicator_name == 'MACD' and 'MACD_12_26_9' in macd.columns:
                    our_values = macd['MACD_12_26_9'].dropna()
                elif indicator_name == 'MACD_Signal' and 'MACDs_12_26_9' in macd.columns:
                    our_values = macd['MACDs_12_26_9'].dropna()
                else:
                    continue
                    
        elif indicator_name == 'Stochastic_%D':
            # EXACT feature-eng logic
            stoch = ta.stoch(data['High'], data['Low'], data['Close'])  # Default %K, %D values
            if stoch is not None:
                print(f"Stoch columns: {stoch.columns.tolist()}")
                if 'STOCHd_14_3_3' in stoch.columns:
                    our_values = stoch['STOCHd_14_3_3'].dropna()
                else:
                    continue
                    
        elif indicator_name == 'ADX':
            # EXACT feature-eng logic
            adx = ta.adx(data['High'], data['Low'], data['Close'])  # Default length is 14
            if adx is not None:
                print(f"ADX columns: {adx.columns.tolist()}")
                if 'ADX_14' in adx.columns:
                    our_values = adx['ADX_14'].dropna()
                else:
                    continue
        
        if len(our_values) > 0:
            print(f"Our {indicator_name}: range [{our_values.min():.6f}, {our_values.max():.6f}]")
            print(f"Our {indicator_name} sample: {our_values.iloc[50:55].values}")
            
            # Compare with expected (denormalized d4)
            expected_min = min_vals[indicator_name]
            expected_max = max_vals[indicator_name]
            expected_normalized = normalized_d4[indicator_name].iloc[test_range].dropna()
            expected_denormalized = expected_normalized * (expected_max - expected_min) + expected_min
            
            print(f"Expected {indicator_name}: range [{expected_denormalized.min():.6f}, {expected_denormalized.max():.6f}]")
            print(f"Expected {indicator_name} sample: {expected_denormalized.iloc[50:55].values}")
            
            # Check if there's a simple scaling factor
            if len(expected_denormalized) > 0 and len(our_values) > 0:
                # Find overlapping indices
                common_length = min(len(our_values), len(expected_denormalized))
                our_subset = our_values.iloc[:common_length]
                expected_subset = expected_denormalized.iloc[:common_length]
                
                # Check for scaling relationships
                non_zero_mask = (our_subset != 0) & (expected_subset != 0)
                if non_zero_mask.sum() > 10:
                    ratios = expected_subset[non_zero_mask] / our_subset[non_zero_mask]
                    print(f"Scaling ratios: mean={ratios.mean():.6f}, std={ratios.std():.6f}")
                    if ratios.std() < 0.01:  # Very consistent ratio
                        print(f"*** CONSISTENT SCALING FACTOR: {ratios.mean():.6f} ***")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
