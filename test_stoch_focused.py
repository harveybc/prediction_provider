#!/usr/bin/env python3
"""
Focused test for Stochastic_%D to achieve exact match.
"""

import pandas as pd
import numpy as np
import json
import pandas_ta as ta
from scipy.stats import skew, kurtosis

def main():
    print("=== Focused Stochastic_%D Test ===\n")
    
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
    
    # Calculate Stochastic on the full dataset
    ohlc_df.columns = ['Open', 'High', 'Low', 'Close']
    stoch = ta.stoch(ohlc_df['High'], ohlc_df['Low'], ohlc_df['Close'])
    raw_stoch_d = stoch['STOCHd_14_3_3']
    
    print(f"Raw Stochastic_%D calculated for {len(raw_stoch_d)} rows")
    print(f"NaN count: {raw_stoch_d.isna().sum()}")
    print(f"First valid index: {raw_stoch_d.first_valid_index()}")
    
    # Apply log transformation as in feature-eng
    def apply_log_transformation(data):
        clean_data = data.dropna()
        if len(clean_data) == 0:
            return data
            
        skewness_original = skew(clean_data)
        kurtosis_original = kurtosis(clean_data)
        normality_score_original = abs(skewness_original) + abs(kurtosis_original)
        
        # Prepare for log transformation
        if (clean_data <= 0).any():
            min_value = clean_data.min()
            shifted_data = clean_data - min_value + 1
        else:
            shifted_data = clean_data
            
        log_transformed_clean = np.log(shifted_data)
        
        skewness_log = skew(log_transformed_clean)
        kurtosis_log = kurtosis(log_transformed_clean)
        normality_score_log = abs(skewness_log) + abs(kurtosis_log)
        
        if normality_score_log < normality_score_original:
            # Apply log transformation to full series
            if (data <= 0).any():
                min_value = data.min()
                full_shifted = data - min_value + 1
            else:
                full_shifted = data
            return np.log(full_shifted.clip(lower=1e-8))
        else:
            return data
    
    transformed_stoch_d = apply_log_transformation(raw_stoch_d)
    print(f"Transformed Stochastic_%D range: [{transformed_stoch_d.min():.6f}, {transformed_stoch_d.max():.6f}]")
    
    # Normalize the transformed data
    min_val = norm_params['Stochastic_%D']['min']
    max_val = norm_params['Stochastic_%D']['max']
    normalized_calc = (transformed_stoch_d - min_val) / (max_val - min_val)
    
    print(f"Normalized calculated range: [{normalized_calc.min():.6f}, {normalized_calc.max():.6f}]")
    
    # Compare with reference data (skip first 200 rows for alignment)
    reference_stoch_d = normalized_df['Stochastic_%D'].iloc[200:1200]
    calculated_stoch_d = normalized_calc.iloc[200:1200]
    
    print(f"\nComparison (rows 200-1200):")
    print(f"Reference range: [{reference_stoch_d.min():.6f}, {reference_stoch_d.max():.6f}]")
    print(f"Calculated range: [{calculated_stoch_d.min():.6f}, {calculated_stoch_d.max():.6f}]")
    
    # Check exact match
    diff = np.abs(reference_stoch_d - calculated_stoch_d)
    max_diff = diff.max()
    mean_diff = diff.mean()
    
    print(f"Max difference: {max_diff:.8f}")
    print(f"Mean difference: {mean_diff:.8f}")
    print(f"Within tolerance (1e-4): {max_diff < 1e-4}")
    
    if max_diff >= 1e-4:
        print("\nFirst 10 differences:")
        for i in range(10):
            if i < len(diff):
                print(f"  Row {i}: ref={reference_stoch_d.iloc[i]:.6f}, calc={calculated_stoch_d.iloc[i]:.6f}, diff={diff.iloc[i]:.6f}")

if __name__ == "__main__":
    main()
