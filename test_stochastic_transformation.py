#!/usr/bin/env python3
"""
Test the exact feature-eng transformation on raw stochastic data
"""

import pandas as pd
import numpy as np
import json
import pandas_ta as ta
from scipy.stats import skew, kurtosis

def test_stochastic_transformation():
    """Test the feature-eng transformation on stochastic data."""
    
    # Load the reference data
    normalized_df = pd.read_csv("/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv")
    
    with open("/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json", 'r') as f:
        debug_data = json.load(f)
    
    # Denormalize OHLC exactly like our test
    hloc_columns = ['OPEN', 'HIGH', 'LOW', 'CLOSE']
    denormalized_data = normalized_df.copy()
    for col in hloc_columns:
        if col in debug_data:
            min_val = debug_data[col]['min']
            max_val = debug_data[col]['max']
            denormalized_data[col] = normalized_df[col] * (max_val - min_val) + min_val
    
    # Prepare OHLC data for pandas_ta
    ohlc_data = pd.DataFrame({
        'High': denormalized_data['HIGH'], 
        'Low': denormalized_data['LOW'],
        'Close': denormalized_data['CLOSE']
    })
    
    # Calculate raw stochastic
    stoch = ta.stoch(ohlc_data['High'], ohlc_data['Low'], ohlc_data['Close'])
    raw_stoch_d = stoch['STOCHd_14_3_3']
    
    print(f"Raw Stochastic_%D:")
    print(f"  Range: [{raw_stoch_d.dropna().min():.6f}, {raw_stoch_d.dropna().max():.6f}]")
    print(f"  At index 200: {raw_stoch_d.iloc[200]:.6f}")
    print(f"  Has negative/zero values: {(raw_stoch_d <= 0).any()}")
    
    # Apply feature-eng transformation logic exactly
    data = raw_stoch_d.fillna(raw_stoch_d.mean())  # Handle missing values
    
    # Analyze original data normality
    skewness_original = skew(data)
    kurtosis_original = kurtosis(data)
    
    # Apply log transformation if data allows it
    if (data <= 0).any():
        # Shift data to make it all positive for log transformation
        min_value = data.min()
        shifted_data = data - min_value + 1
        print(f"  Data shifted by {-min_value + 1:.6f} to make positive")
    else:
        shifted_data = data
        print(f"  Data already positive, no shift needed")
    
    log_transformed_data = np.log(shifted_data)
    
    # Analyze log-transformed data normality
    skewness_log = skew(log_transformed_data)
    kurtosis_log = kurtosis(log_transformed_data)
    
    # Decide whether to use log-transformed data or original data
    normality_score_original = abs(skewness_original) + abs(kurtosis_original)
    normality_score_log = abs(skewness_log) + abs(kurtosis_log)
    
    print(f"\nNormality analysis:")
    print(f"  Original: skew={skewness_original:.6f}, kurt={kurtosis_original:.6f}, score={normality_score_original:.6f}")
    print(f"  Log: skew={skewness_log:.6f}, kurt={kurtosis_log:.6f}, score={normality_score_log:.6f}")
    
    if normality_score_log < normality_score_original:
        print(f"  Decision: Using log-transformed data (improved normality)")
        final_data = log_transformed_data
    else:
        print(f"  Decision: Using original data (log did not improve normality)")
        final_data = data
    
    print(f"\nFinal transformed data:")
    print(f"  Range: [{final_data.dropna().min():.6f}, {final_data.dropna().max():.6f}]")
    print(f"  At index 200: {final_data.iloc[200]:.6f}")
    
    # Compare with reference
    min_val = debug_data['Stochastic_%D']['min']
    max_val = debug_data['Stochastic_%D']['max']
    reference_normalized = normalized_df['Stochastic_%D']
    reference_denormalized = reference_normalized * (max_val - min_val) + min_val
    
    print(f"\nReference denormalized data:")
    print(f"  Range: [{reference_denormalized.min():.6f}, {reference_denormalized.max():.6f}]")
    print(f"  At index 200: {reference_denormalized.iloc[200]:.6f}")
    
    # Check if they match
    diff_at_200 = abs(final_data.iloc[200] - reference_denormalized.iloc[200])
    print(f"\nComparison at index 200:")
    print(f"  Transformed: {final_data.iloc[200]:.6f}")
    print(f"  Reference: {reference_denormalized.iloc[200]:.6f}")
    print(f"  Difference: {diff_at_200:.6f}")
    
    # Check if ranges are even close
    final_range = final_data.dropna().max() - final_data.dropna().min()
    ref_range = reference_denormalized.max() - reference_denormalized.min()
    print(f"\nRange comparison:")
    print(f"  Transformed range span: {final_range:.6f}")
    print(f"  Reference range span: {ref_range:.6f}")
    print(f"  Range ratio: {final_range / ref_range:.2f}")

if __name__ == "__main__":
    test_stochastic_transformation()
