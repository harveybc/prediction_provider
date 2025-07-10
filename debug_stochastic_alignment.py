#!/usr/bin/env python3
"""
Debug Stochastic_%D alignment and normalization issues
"""

import pandas as pd
import numpy as np
import json

# Load the normalized reference data
normalized_df = pd.read_csv("/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv")

# Load normalization parameters
with open("/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json", 'r') as f:
    norm_params = json.load(f)

# Get Stochastic_%D data
stoch_d_normalized = normalized_df['Stochastic_%D']
min_val = norm_params['Stochastic_%D']['min']
max_val = norm_params['Stochastic_%D']['max']

print(f"Reference normalized Stochastic_%D:")
print(f"  Range: [{stoch_d_normalized.min():.6f}, {stoch_d_normalized.max():.6f}]")
print(f"  First 10: {stoch_d_normalized.iloc[:10].tolist()}")
print(f"  Shape: {stoch_d_normalized.shape}")

# Denormalize
stoch_d_denormalized = stoch_d_normalized * (max_val - min_val) + min_val
print(f"\nDenormalized Stochastic_%D:")
print(f"  Range: [{stoch_d_denormalized.min():.6f}, {stoch_d_denormalized.max():.6f}]")
print(f"  First 10: {stoch_d_denormalized.iloc[:10].tolist()}")

# Re-normalize using same formula as DataNormalizer
stoch_d_renormalized = (stoch_d_denormalized - min_val) / (max_val - min_val)
print(f"\nRe-normalized Stochastic_%D:")
print(f"  Range: [{stoch_d_renormalized.min():.6f}, {stoch_d_renormalized.max():.6f}]")
print(f"  First 10: {stoch_d_renormalized.iloc[:10].tolist()}")

# Check differences
diff = np.abs(stoch_d_normalized - stoch_d_renormalized)
print(f"\nDifference between original normalized and re-normalized:")
print(f"  Max diff: {diff.max():.10f}")
print(f"  Mean diff: {diff.mean():.10f}")
print(f"  Are they identical? {np.allclose(stoch_d_normalized, stoch_d_renormalized, atol=1e-15)}")

# Now check what happens with aligned window offset of 200
window_offset = 200
aligned_original = stoch_d_normalized.iloc[window_offset:window_offset+1000]
aligned_renormalized = stoch_d_renormalized.iloc[window_offset:window_offset+1000]

print(f"\nWith window offset {window_offset} (first 1000 rows):")
print(f"Original aligned range: [{aligned_original.min():.6f}, {aligned_original.max():.6f}]")
print(f"Renormalized aligned range: [{aligned_renormalized.min():.6f}, {aligned_renormalized.max():.6f}]")

aligned_diff = np.abs(aligned_original - aligned_renormalized)
print(f"Aligned difference:")
print(f"  Max diff: {aligned_diff.max():.10f}")
print(f"  Mean diff: {aligned_diff.mean():.10f}")

# Check normalization parameters
print(f"\nNormalization parameters:")
print(f"  min_val: {min_val}")
print(f"  max_val: {max_val}")
print(f"  range: {max_val - min_val}")
