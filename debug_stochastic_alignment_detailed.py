#!/usr/bin/env python3
"""
Debug the exact alignment between raw stochastic and reference data
"""

import pandas as pd
import numpy as np
import json
import pandas_ta as ta

# Load reference data
normalized_df = pd.read_csv("/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv")

with open("/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json", 'r') as f:
    debug_data = json.load(f)

min_vals = {}
max_vals = {}
for feature, values in debug_data.items():
    min_vals[feature] = values['min']
    max_vals[feature] = values['max']

# Denormalize HLOC exactly like the test
hloc_columns = ['OPEN', 'HIGH', 'LOW', 'CLOSE']
denormalized_data = normalized_df.copy()

for col in hloc_columns:
    if col in min_vals and col in max_vals:
        min_val = min_vals[col]
        max_val = max_vals[col]
        denormalized_data[col] = normalized_df[col] * (max_val - min_val) + min_val

# Prepare HLOC data for pandas_ta
ohlc_data = pd.DataFrame({
    'Open': denormalized_data['OPEN'],
    'High': denormalized_data['HIGH'], 
    'Low': denormalized_data['LOW'],
    'Close': denormalized_data['CLOSE']
})

print("Calculating raw Stochastic indicator...")
stoch = ta.stoch(ohlc_data['High'], ohlc_data['Low'], ohlc_data['Close'])

if stoch is not None and 'STOCHd_14_3_3' in stoch.columns:
    raw_stoch_d = stoch['STOCHd_14_3_3']
    
    print(f"Raw Stochastic_%D:")
    print(f"  Shape: {raw_stoch_d.shape}")
    print(f"  NaN count: {raw_stoch_d.isna().sum()}")
    print(f"  First valid index: {raw_stoch_d.first_valid_index()}")
    print(f"  Range (non-NaN): [{raw_stoch_d.dropna().min():.6f}, {raw_stoch_d.dropna().max():.6f}]")
    print(f"  Values around first valid index:")
    for i in range(15, 25):
        print(f"    Index {i}: {raw_stoch_d.iloc[i]}")
    
    # Get reference data
    reference_normalized = normalized_df['Stochastic_%D']
    min_val = min_vals['Stochastic_%D']
    max_val = max_vals['Stochastic_%D']
    reference_denormalized = reference_normalized * (max_val - min_val) + min_val
    
    print(f"\nReference Stochastic_%D (denormalized):")
    print(f"  Shape: {reference_denormalized.shape}")
    print(f"  Range: [{reference_denormalized.min():.6f}, {reference_denormalized.max():.6f}]")
    print(f"  Values at indices 0-24:")
    for i in range(25):
        print(f"    Index {i}: {reference_denormalized.iloc[i]:.6f}")
    
    # Compare with specific window offset that the test uses
    window_offset = 200
    
    print(f"\nComparison at window offset {window_offset}:")
    print(f"  Raw Stochastic_%D at index {window_offset}: {raw_stoch_d.iloc[window_offset]}")
    print(f"  Reference at index {window_offset}: {reference_denormalized.iloc[window_offset]:.6f}")
    
    # See what the alignment should be for indices 200-205
    print(f"\nDetailed comparison for indices 200-205:")
    for i in range(200, 206):
        raw_val = raw_stoch_d.iloc[i] if not pd.isna(raw_stoch_d.iloc[i]) else "NaN"
        ref_val = reference_denormalized.iloc[i]
        print(f"  Index {i}: Raw={raw_val}, Ref={ref_val:.6f}")
        
    # Check if raw and reference are similar in any range
    print(f"\nLooking for matching patterns...")
    first_valid = raw_stoch_d.first_valid_index()
    print(f"Raw first valid index: {first_valid}")
    
    # Compare raw at first_valid vs reference at various offsets
    raw_val_at_first = raw_stoch_d.iloc[first_valid]
    print(f"Raw value at first valid ({first_valid}): {raw_val_at_first}")
    
    # Look for this value in reference data
    for offset in range(0, 30):
        ref_val = reference_denormalized.iloc[offset]
        diff = abs(raw_val_at_first - ref_val)
        if diff < 0.1:  # Close match
            print(f"  Potential match: Raw[{first_valid}]={raw_val_at_first:.6f} ≈ Ref[{offset}]={ref_val:.6f} (diff={diff:.6f})")

else:
    print("Failed to calculate raw Stochastic indicator!")
