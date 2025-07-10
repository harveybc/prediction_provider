#!/usr/bin/env python3
"""
Debug Stochastic_%D mapping issue.
"""

import pandas as pd
import numpy as np
import json

def main():
    print("=== Debugging Stochastic_%D Mapping ===\n")
    
    # Load data
    normalized_df = pd.read_csv('/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv')
    
    with open('/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json', 'r') as f:
        norm_params = json.load(f)
    
    # Get reference data
    reference_normalized = normalized_df['Stochastic_%D']
    min_val = norm_params['Stochastic_%D']['min']
    max_val = norm_params['Stochastic_%D']['max']
    reference_denormalized = reference_normalized * (max_val - min_val) + min_val
    
    print(f"Reference normalized range: [{reference_normalized.min():.6f}, {reference_normalized.max():.6f}]")
    print(f"Normalization params: min={min_val:.6f}, max={max_val:.6f}")
    print(f"Reference denormalized range: [{reference_denormalized.min():.6f}, {reference_denormalized.max():.6f}]")
    
    # Test normalization round-trip
    test_normalized = (reference_denormalized - min_val) / (max_val - min_val)
    print(f"Round-trip normalized range: [{test_normalized.min():.6f}, {test_normalized.max():.6f}]")
    
    # Check differences
    diff = np.abs(reference_normalized - test_normalized)
    print(f"Round-trip max diff: {diff.max():.8f}")
    print(f"Round-trip mean diff: {diff.mean():.8f}")
    
    # Check for validation region (200-1200)
    validation_region = slice(200, 1200)
    ref_val = reference_normalized.iloc[validation_region]
    test_val = test_normalized.iloc[validation_region]
    val_diff = np.abs(ref_val - test_val)
    
    print(f"\nValidation region (200-1200):")
    print(f"Reference range: [{ref_val.min():.6f}, {ref_val.max():.6f}]")
    print(f"Test range: [{test_val.min():.6f}, {test_val.max():.6f}]")
    print(f"Validation max diff: {val_diff.max():.8f}")
    print(f"Validation mean diff: {val_diff.mean():.8f}")
    
    if val_diff.max() > 1e-8:
        print("\nFirst 10 differences in validation region:")
        for i in range(10):
            idx = 200 + i
            if idx < len(reference_normalized):
                ref = reference_normalized.iloc[idx]
                test = test_normalized.iloc[idx]
                diff_val = abs(ref - test)
                print(f"  Row {idx}: ref={ref:.8f}, test={test:.8f}, diff={diff_val:.8f}")

if __name__ == "__main__":
    main()
