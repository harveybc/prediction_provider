#!/usr/bin/env python3
"""
Compare the exact OHLC values being used for stochastic calculation
"""

import pandas as pd
import numpy as np
import json
import pandas_ta as ta

def compare_ohlc_values():
    """Compare OHLC values used in our test vs what feature-eng would use."""
    
    # Load the reference data
    normalized_df = pd.read_csv("/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv")
    
    with open("/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json", 'r') as f:
        debug_data = json.load(f)
    
    # Get normalization parameters for OHLC
    hloc_columns = ['OPEN', 'HIGH', 'LOW', 'CLOSE']
    
    print("Normalization parameters for OHLC:")
    for col in hloc_columns:
        if col in debug_data:
            min_val = debug_data[col]['min']
            max_val = debug_data[col]['max']
            print(f"  {col}: min={min_val:.10f}, max={max_val:.10f}")
    
    # Denormalize OHLC exactly like our test
    denormalized_data = normalized_df.copy()
    for col in hloc_columns:
        if col in debug_data:
            min_val = debug_data[col]['min']
            max_val = debug_data[col]['max']
            denormalized_data[col] = normalized_df[col] * (max_val - min_val) + min_val
    
    # Convert to feature-eng format (matching their adjust_ohlc method)
    # Normalize column names to lowercase first
    feature_eng_data = denormalized_data[hloc_columns].copy()
    feature_eng_data.columns = feature_eng_data.columns.str.lower()
    
    # Apply renaming like feature-eng does
    renaming_map = {'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close'}
    feature_eng_data = feature_eng_data.rename(columns=renaming_map)
    
    # Our test format
    our_test_data = pd.DataFrame({
        'Open': denormalized_data['OPEN'],
        'High': denormalized_data['HIGH'], 
        'Low': denormalized_data['LOW'],
        'Close': denormalized_data['CLOSE']
    })
    
    print(f"\nData comparison at indices 200-205:")
    for i in range(200, 206):
        print(f"\nIndex {i}:")
        for col in ['Open', 'High', 'Low', 'Close']:
            feature_eng_val = feature_eng_data[col].iloc[i]
            our_test_val = our_test_data[col].iloc[i]
            diff = abs(feature_eng_val - our_test_val)
            print(f"  {col}: feature-eng={feature_eng_val:.15f}, our_test={our_test_val:.15f}, diff={diff:.15f}")
    
    # Check if the differences are significant
    print(f"\nChecking for significant differences:")
    for col in ['Open', 'High', 'Low', 'Close']:
        max_diff = np.abs(feature_eng_data[col] - our_test_data[col]).max()
        print(f"  {col} max difference: {max_diff:.15f}")
        if max_diff > 1e-10:
            print(f"    WARNING: Significant difference detected!")
    
    # Now calculate stochastic with both datasets
    print(f"\nCalculating stochastic with both datasets:")
    
    # Feature-eng style calculation
    stoch_feature_eng = ta.stoch(feature_eng_data['High'], feature_eng_data['Low'], feature_eng_data['Close'])
    
    # Our test style calculation  
    stoch_our_test = ta.stoch(our_test_data['High'], our_test_data['Low'], our_test_data['Close'])
    
    if stoch_feature_eng is not None and 'STOCHd_14_3_3' in stoch_feature_eng.columns:
        stoch_d_feature_eng = stoch_feature_eng['STOCHd_14_3_3']
        print(f"Feature-eng stochastic_%D range: [{stoch_d_feature_eng.dropna().min():.6f}, {stoch_d_feature_eng.dropna().max():.6f}]")
        print(f"Feature-eng stochastic_%D at index 200: {stoch_d_feature_eng.iloc[200]:.15f}")
    
    if stoch_our_test is not None and 'STOCHd_14_3_3' in stoch_our_test.columns:
        stoch_d_our_test = stoch_our_test['STOCHd_14_3_3']
        print(f"Our test stochastic_%D range: [{stoch_d_our_test.dropna().min():.6f}, {stoch_d_our_test.dropna().max():.6f}]")
        print(f"Our test stochastic_%D at index 200: {stoch_d_our_test.iloc[200]:.15f}")
    
    # Compare the stochastic values
    if (stoch_feature_eng is not None and 'STOCHd_14_3_3' in stoch_feature_eng.columns and
        stoch_our_test is not None and 'STOCHd_14_3_3' in stoch_our_test.columns):
        
        stoch_diff = np.abs(stoch_d_feature_eng - stoch_d_our_test)
        print(f"\nStochastic_%D differences:")
        print(f"  Max difference: {stoch_diff.max():.15f}")
        print(f"  Mean difference (non-NaN): {stoch_diff.dropna().mean():.15f}")
        
        # Check specific indices
        for i in range(200, 206):
            if not pd.isna(stoch_d_feature_eng.iloc[i]) and not pd.isna(stoch_d_our_test.iloc[i]):
                diff = abs(stoch_d_feature_eng.iloc[i] - stoch_d_our_test.iloc[i])
                print(f"  Index {i}: diff={diff:.15f}")
    
    # Compare with reference denormalized values
    print(f"\nComparing with reference denormalized stochastic_%D:")
    reference_normalized = normalized_df['Stochastic_%D']
    min_val = debug_data['Stochastic_%D']['min']
    max_val = debug_data['Stochastic_%D']['max']
    reference_denormalized = reference_normalized * (max_val - min_val) + min_val
    
    print(f"Reference denormalized at index 200: {reference_denormalized.iloc[200]:.15f}")
    
    if stoch_our_test is not None and 'STOCHd_14_3_3' in stoch_our_test.columns:
        calculated_at_200 = stoch_d_our_test.iloc[200]
        if not pd.isna(calculated_at_200):
            diff_vs_ref = abs(calculated_at_200 - reference_denormalized.iloc[200])
            print(f"Difference vs reference: {diff_vs_ref:.15f}")

if __name__ == "__main__":
    compare_ohlc_values()
