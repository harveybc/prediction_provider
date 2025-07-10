#!/usr/bin/env python3
"""
Debug the exact values being compared for Stochastic_%D.
"""

import sys
sys.path.append('/home/harveybc/Documents/GitHub/prediction_provider/plugins_feeder')

import pandas as pd
import numpy as np
import json
from technical_indicators import TechnicalIndicatorCalculator

def main():
    print("=== Debugging Stochastic_%D Exact Values ===\n")
    
    # Load reference data
    normalized_df = pd.read_csv('/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv')
    
    with open('/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json', 'r') as f:
        norm_params = json.load(f)
    
    print("Loading and denormalizing OHLC data...")
    
    # Denormalize OHLC data (same as in the test)
    ohlc_columns = ['OPEN', 'HIGH', 'LOW', 'CLOSE']
    denormalized_data = {}
    
    for col in ohlc_columns:
        if col in normalized_df.columns and col in norm_params:
            min_val = norm_params[col]['min']
            max_val = norm_params[col]['max']
            denormalized_data[col] = normalized_df[col] * (max_val - min_val) + min_val
    
    hloc_data = pd.DataFrame(denormalized_data)
    
    print("Recalculating technical indicators...")
    calculator = TechnicalIndicatorCalculator()
    indicators_df = calculator.calculate_all_indicators(hloc_data)
    
    print(f"Indicators calculated. Stochastic_%D shape: {indicators_df['Stochastic_%D'].shape}")
    
    # Get the exact values from validation window (200:1200)
    validation_start = 200
    validation_end = 1200
    
    # Reference values (normalized)
    ref_normalized = normalized_df['Stochastic_%D'].iloc[validation_start:validation_end]
    
    # Calculated values (need to normalize them)
    calc_denormalized = indicators_df['Stochastic_%D'].iloc[validation_start:validation_end]
    min_val = norm_params['Stochastic_%D']['min']
    max_val = norm_params['Stochastic_%D']['max']
    calc_normalized = (calc_denormalized - min_val) / (max_val - min_val)
    
    print(f"\nValidation window: {validation_start} to {validation_end}")
    print(f"Reference normalized shape: {ref_normalized.shape}")
    print(f"Calculated normalized shape: {calc_normalized.shape}")
    
    print(f"\nFirst 10 reference normalized: {ref_normalized.iloc[:10].tolist()}")
    print(f"First 10 calculated normalized: {calc_normalized.iloc[:10].tolist()}")
    
    # Calculate differences
    diff = np.abs(ref_normalized.values - calc_normalized.values)
    print(f"\nFirst 10 differences: {diff[:10].tolist()}")
    print(f"Max difference: {diff.max():.8f}")
    print(f"Mean difference: {diff.mean():.8f}")
    
    # Check if there's an index mismatch
    print(f"\nIndex comparison:")
    print(f"Reference index range: {ref_normalized.index.min()} to {ref_normalized.index.max()}")
    print(f"Calculated index range: {calc_normalized.index.min()} to {calc_normalized.index.max()}")
    
    if diff.max() > 1e-4:
        print(f"\n❌ Still failing with max diff: {diff.max():.8f}")
        
        # Find the problematic values
        max_diff_idx = np.argmax(diff)
        print(f"Max difference at index {max_diff_idx}:")
        print(f"  Reference: {ref_normalized.iloc[max_diff_idx]:.8f}")
        print(f"  Calculated: {calc_normalized.iloc[max_diff_idx]:.8f}")
        print(f"  Difference: {diff[max_diff_idx]:.8f}")
    else:
        print(f"\n✅ SUCCESS! Max diff {diff.max():.8f} is within tolerance")

if __name__ == "__main__":
    main()
