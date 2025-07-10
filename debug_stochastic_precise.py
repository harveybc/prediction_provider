#!/usr/bin/env python3
"""
Precise debugging of Stochastic_%D transformation to achieve exact match.
"""

import pandas as pd
import numpy as np
import json
import pandas_ta as ta
from scipy.stats import skew, kurtosis

def load_and_prepare_data():
    """Load and prepare the test data."""
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
    return ohlc_df, normalized_df, norm_params

def test_stochastic_transformation():
    """Test different transformations for Stochastic_%D to find exact match."""
    print("=== Precise Stochastic_%D Debugging ===\n")
    
    ohlc_df, normalized_df, norm_params = load_and_prepare_data()
    
    # Use first 1200 rows for calculation
    ohlc_subset = ohlc_df.iloc[:1200].copy()
    ohlc_subset.columns = ['Open', 'High', 'Low', 'Close']
    
    # Calculate Stochastic
    stoch = ta.stoch(ohlc_subset['High'], ohlc_subset['Low'], ohlc_subset['Close'])
    raw_stoch_d = stoch['STOCHd_14_3_3']
    
    print(f"Raw Stochastic_%D range: [{raw_stoch_d.min():.6f}, {raw_stoch_d.max():.6f}]")
    
    # Get expected values (denormalized from normalized_d4.csv)
    stoch_d_norm_params = norm_params['Stochastic_%D']
    min_val = stoch_d_norm_params['min']
    max_val = stoch_d_norm_params['max']
    
    # Get corresponding section from normalized data (offset by 200 for indicators)
    normalized_stoch_d = normalized_df['Stochastic_%D'].iloc[200:1200]
    expected_values = normalized_stoch_d * (max_val - min_val) + min_val
    
    print(f"Expected Stochastic_%D range: [{expected_values.min():.6f}, {expected_values.max():.6f}]")
    print(f"Expected first 10 values: {expected_values.iloc[:10].values}")
    
    # Test different transformations
    print("\n=== Testing Transformations ===")
    
    # 1. Original data
    print("\n1. Original Raw Data:")
    aligned_raw = raw_stoch_d.iloc[:1000]  # Align with expected
    print(f"Range: [{aligned_raw.min():.6f}, {aligned_raw.max():.6f}]")
    print(f"First 10: {aligned_raw.iloc[:10].values}")
    
    # 2. Log transformation
    print("\n2. Log Transformation:")
    if (aligned_raw <= 0).any():
        min_value = aligned_raw.min()
        shifted_data = aligned_raw - min_value + 1
    else:
        shifted_data = aligned_raw
    log_transformed = np.log(shifted_data)
    print(f"Range: [{log_transformed.min():.6f}, {log_transformed.max():.6f}]")
    print(f"First 10: {log_transformed.iloc[:10].values}")
    
    # 3. Square root transformation
    print("\n3. Square Root Transformation:")
    sqrt_transformed = np.sqrt(aligned_raw)
    print(f"Range: [{sqrt_transformed.min():.6f}, {sqrt_transformed.max():.6f}]") 
    print(f"First 10: {sqrt_transformed.iloc[:10].values}")
    
    # 4. Inverse transformation
    print("\n4. Inverse Transformation:")
    inv_transformed = 1.0 / aligned_raw
    print(f"Range: [{inv_transformed.min():.6f}, {inv_transformed.max():.6f}]")
    print(f"First 10: {inv_transformed.iloc[:10].values}")
    
    # 5. Custom scaling to match expected range
    print("\n5. Custom Scaling to Match Expected Range:")
    # Scale from [raw_min, raw_max] to [expected_min, expected_max]
    raw_min, raw_max = aligned_raw.min(), aligned_raw.max()
    exp_min, exp_max = expected_values.min(), expected_values.max()
    scaled = (aligned_raw - raw_min) / (raw_max - raw_min) * (exp_max - exp_min) + exp_min
    print(f"Range: [{scaled.min():.6f}, {scaled.max():.6f}]")
    print(f"First 10: {scaled.iloc[:10].values}")
    
    # Compare scaled version with expected
    diff = np.abs(scaled.iloc[:10] - expected_values.iloc[:10])
    print(f"Differences from expected (first 10): {diff.values}")
    print(f"Max diff in first 10: {diff.max():.6f}")

if __name__ == "__main__":
    test_stochastic_transformation()
