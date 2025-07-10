#!/usr/bin/env python3
"""
Analyze all columns in normalized_d4.csv to see which ones have similar ranges
to the Stochastic_%D column, and check if our calculation might be matching
a different column.
"""

import pandas as pd
import numpy as np
import json

def analyze_column_ranges():
    """Analyze ranges of all columns in the normalized dataset."""
    print("=== Analyzing Column Ranges in normalized_d4.csv ===\n")
    
    # Load data
    d4_path = '/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv'
    normalized_d4 = pd.read_csv(d4_path)
    
    debug_path = '/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json'
    with open(debug_path, 'r') as f:
        debug_data = json.load(f)
    
    print(f"Dataset shape: {normalized_d4.shape}")
    print(f"Columns: {list(normalized_d4.columns)}")
    
    # Get the range of Stochastic_%D for comparison
    stoch_d_col = normalized_d4['Stochastic_%D']
    min_val = debug_data['Stochastic_%D']['min']
    max_val = debug_data['Stochastic_%D']['max']
    stoch_d_denormalized = stoch_d_col * (max_val - min_val) + min_val
    
    target_min = stoch_d_denormalized.min()
    target_max = stoch_d_denormalized.max()
    target_range = target_max - target_min
    
    print(f"\nTarget (Stochastic_%D) denormalized range: [{target_min:.6f}, {target_max:.6f}] (range: {target_range:.6f})")
    
    # Analyze all columns
    print(f"\n=== Column Range Analysis ===")
    similar_columns = []
    
    for col in normalized_d4.columns:
        if col in debug_data and col != 'Stochastic_%D':
            col_data = normalized_d4[col]
            col_min = debug_data[col]['min']
            col_max = debug_data[col]['max']
            col_denormalized = col_data * (col_max - col_min) + col_min
            
            col_range_min = col_denormalized.min()
            col_range_max = col_denormalized.max()
            col_range = col_range_max - col_range_min
            
            # Check if this column has a similar range to our target
            range_similarity = abs(col_range - target_range) / target_range if target_range > 0 else float('inf')
            min_similarity = abs(col_range_min - target_min) / abs(target_min) if target_min != 0 else float('inf')
            max_similarity = abs(col_range_max - target_max) / abs(target_max) if target_max != 0 else float('inf')
            
            print(f"{col:20s}: [{col_range_min:8.4f}, {col_range_max:8.4f}] (range: {col_range:8.4f}) - Range sim: {range_similarity:.2f}")
            
            # Flag columns with similar characteristics
            if range_similarity < 0.5 or (min_similarity < 0.5 and max_similarity < 0.5):
                similar_columns.append((col, range_similarity, min_similarity, max_similarity))
    
    if similar_columns:
        print(f"\n=== Columns with Similar Ranges ===")
        for col, range_sim, min_sim, max_sim in similar_columns:
            print(f"{col}: Range similarity: {range_sim:.3f}, Min similarity: {min_sim:.3f}, Max similarity: {max_sim:.3f}")
    
    # Check if our standard stochastic calculation matches any other column
    print(f"\n=== Checking if Standard Stochastic Matches Other Columns ===")
    
    # Load our calculated stochastic for comparison
    import sys
    sys.path.append('/home/harveybc/Documents/GitHub/prediction_provider/plugins_feeder')
    from technical_indicators import TechnicalIndicatorCalculator
    
    normalized_d4_full, min_vals, max_vals = load_test_data()
    ohlc_data = denormalize_ohlc(normalized_d4_full, min_vals, max_vals)
    
    calculator = TechnicalIndicatorCalculator()
    indicators = calculator.calculate_all_indicators(ohlc_data)
    
    our_stoch_d = indicators['Stochastic_%D'].dropna()
    our_stoch_k = indicators['Stochastic_%K'].dropna()
    
    print(f"Our Stochastic_%D range: [{our_stoch_d.min():.4f}, {our_stoch_d.max():.4f}]")
    print(f"Our Stochastic_%K range: [{our_stoch_k.min():.4f}, {our_stoch_k.max():.4f}]")
    
    # Check if our values match any column when properly aligned
    first_valid_idx = indicators['Stochastic_%D'].first_valid_index()
    if first_valid_idx is not None:
        offset = indicators['Stochastic_%D'].index.get_loc(first_valid_idx)
        
        for col in ['Stochastic_%K', 'RSI', 'ADX', 'DI+', 'DI-', 'CCI', 'WilliamsR']:
            if col in normalized_d4.columns and col in debug_data:
                # Denormalize the reference column
                ref_col_data = normalized_d4[col]
                ref_min = debug_data[col]['min']
                ref_max = debug_data[col]['max']
                ref_denormalized = ref_col_data * (ref_max - ref_min) + ref_min
                
                # Align data
                our_values = our_stoch_d.head(1000).values if len(our_stoch_d) >= 1000 else our_stoch_d.values
                ref_values = ref_denormalized.iloc[offset:offset + len(our_values)].values
                
                min_length = min(len(our_values), len(ref_values))
                if min_length > 100:  # Need enough data for meaningful comparison
                    our_values = our_values[:min_length]
                    ref_values = ref_values[:min_length]
                    
                    max_diff = np.abs(our_values - ref_values).max()
                    mean_diff = np.abs(our_values - ref_values).mean()
                    
                    print(f"vs {col:15s}: Max diff: {max_diff:8.4f}, Mean diff: {mean_diff:8.4f}")
                    
                    if max_diff < 1.0:  # Reasonably close
                        print(f"  🔍 POTENTIAL MATCH: {col} - investigating further...")
                        print(f"    Our first 5 values:  {our_values[:5]}")
                        print(f"    {col} first 5 values: {ref_values[:5]}")
    
    # Special check: Does our Stochastic_%D match the ADX column?
    print(f"\n=== SPECIAL CHECK: Our Stochastic_%D vs Reference ADX ===")
    if 'ADX' in normalized_d4.columns and 'ADX' in debug_data:
        ref_adx_data = normalized_d4['ADX']
        ref_adx_min = debug_data['ADX']['min']
        ref_adx_max = debug_data['ADX']['max']
        ref_adx_denormalized = ref_adx_data * (ref_adx_max - ref_adx_min) + ref_adx_min
        
        first_valid_idx = indicators['Stochastic_%D'].first_valid_index()
        if first_valid_idx is not None:
            offset = indicators['Stochastic_%D'].index.get_loc(first_valid_idx)
            
            our_stoch_values = our_stoch_d.head(1000).values if len(our_stoch_d) >= 1000 else our_stoch_d.values
            ref_adx_values = ref_adx_denormalized.iloc[offset:offset + len(our_stoch_values)].values
            
            min_length = min(len(our_stoch_values), len(ref_adx_values))
            our_stoch_values = our_stoch_values[:min_length]
            ref_adx_values = ref_adx_values[:min_length]
            
            if min_length > 0:
                max_diff = np.abs(our_stoch_values - ref_adx_values).max()
                mean_diff = np.abs(our_stoch_values - ref_adx_values).mean()
                
                print(f"Our Stochastic_%D vs Reference ADX:")
                print(f"  Max difference: {max_diff:.6f}")
                print(f"  Mean difference: {mean_diff:.6f}")
                print(f"  Our Stochastic_%D first 5: {our_stoch_values[:5]}")
                print(f"  Reference ADX first 5:     {ref_adx_values[:5]}")
                
                if max_diff < 5.0:
                    print(f"  🎉 POTENTIAL COLUMN MISMATCH DETECTED!")
                    print(f"  Our calculated Stochastic_%D might actually match the ADX column!")
                
    # Check if our ADX matches the reference Stochastic_%D column
    print(f"\n=== REVERSE CHECK: Our ADX vs Reference Stochastic_%D ===")
    if 'ADX' in indicators:
        our_adx = indicators['ADX'].dropna()
        
        if 'Stochastic_%D' in debug_data:
            ref_stoch_d_data = normalized_d4['Stochastic_%D']
            ref_stoch_d_min = debug_data['Stochastic_%D']['min']
            ref_stoch_d_max = debug_data['Stochastic_%D']['max']
            ref_stoch_d_denormalized = ref_stoch_d_data * (ref_stoch_d_max - ref_stoch_d_min) + ref_stoch_d_min
            
            first_valid_idx = indicators['ADX'].first_valid_index()
            if first_valid_idx is not None:
                offset = indicators['ADX'].index.get_loc(first_valid_idx)
                
                our_adx_values = our_adx.head(1000).values if len(our_adx) >= 1000 else our_adx.values
                ref_stoch_d_values = ref_stoch_d_denormalized.iloc[offset:offset + len(our_adx_values)].values
                
                min_length = min(len(our_adx_values), len(ref_stoch_d_values))
                our_adx_values = our_adx_values[:min_length]
                ref_stoch_d_values = ref_stoch_d_values[:min_length]
                
                if min_length > 0:
                    max_diff = np.abs(our_adx_values - ref_stoch_d_values).max()
                    mean_diff = np.abs(our_adx_values - ref_stoch_d_values).mean()
                    
                    print(f"Our ADX vs Reference Stochastic_%D:")
                    print(f"  Max difference: {max_diff:.6f}")
                    print(f"  Mean difference: {mean_diff:.6f}")
                    print(f"  Our ADX first 5:                  {our_adx_values[:5]}")
                    print(f"  Reference Stochastic_%D first 5:  {ref_stoch_d_values[:5]}")
                    
                    if max_diff < 0.1:
                        print(f"  🎉 EXACT MATCH FOUND!")
                        print(f"  Our calculated ADX matches the reference Stochastic_%D column!")
                        print(f"  This confirms a column labeling issue in the original dataset.")

if __name__ == '__main__':
    def load_test_data():
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
        denormalized_data = pd.DataFrame()
        
        for col in ['OPEN', 'HIGH', 'LOW', 'CLOSE']:
            if col in normalized_d4.columns:
                min_val = min_vals[col]
                max_val = max_vals[col]
                denormalized_data[col] = normalized_d4[col] * (max_val - min_val) + min_val
                
        return denormalized_data
    
    analyze_column_ranges()
