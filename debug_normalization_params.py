#!/usr/bin/env python3
"""
Compare normalization parameters used by test vs mapping function
"""

import pandas as pd
import numpy as np
import json

# Load the test normalization parameters (used by test script)
debug_path = '/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json'
with open(debug_path, 'r') as f:
    debug_data = json.load(f)

test_min = debug_data['Stochastic_%D']['min']
test_max = debug_data['Stochastic_%D']['max']

print(f"Test script normalization parameters:")
print(f"  min: {test_min}")
print(f"  max: {test_max}")
print(f"  range: {test_max - test_min}")

# Load what the DataNormalizer would use
try:
    from plugins_feeder.data_normalizer import DataNormalizer
    
    # Check if it uses a different file
    norm_file = "/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json"
    normalizer = DataNormalizer(norm_file)
    
    if 'Stochastic_%D' in normalizer.min_max_values:
        norm_min = normalizer.min_max_values['Stochastic_%D']['min']
        norm_max = normalizer.min_max_values['Stochastic_%D']['max']
        
        print(f"\nDataNormalizer parameters:")
        print(f"  min: {norm_min}")
        print(f"  max: {norm_max}")
        print(f"  range: {norm_max - norm_min}")
        
        print(f"\nParameters match: {test_min == norm_min and test_max == norm_max}")
    else:
        print(f"\nDataNormalizer: Stochastic_%D not found in min_max_values")
        print(f"Available columns: {list(normalizer.min_max_values.keys())[:10]}...")
        
except Exception as e:
    print(f"\nError loading DataNormalizer: {e}")

# Test the normalization with a specific value
test_denorm_value = 3.353826258782347  # The value at index 200

test_normalized = (test_denorm_value - test_min) / (test_max - test_min)
print(f"\nTest normalization of {test_denorm_value}:")
print(f"  Result: {test_normalized:.8f}")

# Check what the expected value should be
normalized_df = pd.read_csv("/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv")
expected_normalized = normalized_df['Stochastic_%D'].iloc[200]
print(f"  Expected: {expected_normalized:.8f}")
print(f"  Match: {abs(test_normalized - expected_normalized) < 1e-10}")

# Check if there's a precision issue
print(f"\nPrecision analysis:")
print(f"  Difference: {abs(test_normalized - expected_normalized):.15f}")

# Reverse check: what denormalized value would give the expected normalized?
expected_denorm = expected_normalized * (test_max - test_min) + test_min
print(f"  Expected denormalized (from normalized): {expected_denorm:.15f}")
print(f"  Actual denormalized: {test_denorm_value:.15f}")
print(f"  Denormalized difference: {abs(expected_denorm - test_denorm_value):.15f}")
