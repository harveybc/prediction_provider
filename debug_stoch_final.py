#!/usr/bin/env python3
"""
Final debug for Stochastic_%D to achieve 100% exact match.
"""

import sys
sys.path.append('/home/harveybc/Documents/GitHub/prediction_provider/plugins_feeder')

import pandas as pd
import numpy as np
import json
from technical_indicators import TechnicalIndicatorCalculator

def main():
    print("=== Final Stochastic_%D Debug ===\n")
    
    # Load test data exactly like the validation test
    normalized_df = pd.read_csv('/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv')
    
    with open('/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json', 'r') as f:
        norm_params = json.load(f)
    
    # Denormalize OHLC data exactly like the test
    ohlc_columns = ['OPEN', 'HIGH', 'LOW', 'CLOSE']
    denormalized_data = {}
    
    for col in ohlc_columns:
        if col in normalized_df.columns and col in norm_params:
            min_val = norm_params[col]['min']
            max_val = norm_params[col]['max']
            denormalized_data[col] = normalized_df[col] * (max_val - min_val) + min_val
    
    ohlc_df = pd.DataFrame(denormalized_data)
    
    # Calculate technical indicators using our calculator
    calculator = TechnicalIndicatorCalculator()
    indicator_df = calculator.calculate_all_indicators(ohlc_df)
    
    # Extract Stochastic_%D from calculated results
    calculated_stoch_d = indicator_df['Stochastic_%D']
    
    # Get reference Stochastic_%D values (what we expect after normalization)
    reference_normalized = normalized_df['Stochastic_%D']
    
    # Normalize calculated values using same logic as test
    min_val = norm_params['Stochastic_%D']['min']
    max_val = norm_params['Stochastic_%D']['max']
    calculated_normalized = (calculated_stoch_d - min_val) / (max_val - min_val)
    
    # Compare in validation region (200-1200)
    window_offset = 200
    max_rows = 1000
    
    ref_aligned = reference_normalized.iloc[window_offset:window_offset+max_rows]
    calc_aligned = calculated_normalized.iloc[window_offset:window_offset+max_rows]
    
    print(f"Reference range: [{ref_aligned.min():.6f}, {ref_aligned.max():.6f}]")
    print(f"Calculated range: [{calc_aligned.min():.6f}, {calc_aligned.max():.6f}]")
    
    # Check differences
    diff = np.abs(ref_aligned - calc_aligned)
    max_diff = diff.max()
    mean_diff = diff.mean()
    
    print(f"Max difference: {max_diff:.8f}")
    print(f"Mean difference: {mean_diff:.8f}")
    print(f"Within tolerance (1e-4): {max_diff < 1e-4}")
    
    if max_diff >= 1e-4:
        print("\nFirst 10 problematic differences:")
        for i in range(min(10, len(diff))):
            if diff.iloc[i] > 1e-4:
                idx = window_offset + i
                ref_val = ref_aligned.iloc[i]
                calc_val = calc_aligned.iloc[i]
                diff_val = diff.iloc[i]
                print(f"  Row {idx}: ref={ref_val:.8f}, calc={calc_val:.8f}, diff={diff_val:.8f}")
    
    print("\nDirect comparison of calculated denormalized vs reference denormalized:")
    calculated_denorm = calculated_stoch_d.iloc[window_offset:window_offset+10]
    reference_denorm = reference_normalized.iloc[window_offset:window_offset+10] * (max_val - min_val) + min_val
    
    print("Calculated denormalized (first 10):", calculated_denorm.values)
    print("Reference denormalized (first 10):", reference_denorm.values)
    print("Denormalized diff (first 10):", np.abs(calculated_denorm - reference_denorm).values)

if __name__ == "__main__":
    main()
