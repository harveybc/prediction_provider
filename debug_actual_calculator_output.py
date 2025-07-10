#!/usr/bin/env python3
"""
Debug the actual values returned by TechnicalIndicatorCalculator
"""

import pandas as pd
import numpy as np
import json
import sys
import os

# Add the plugins_feeder directory to the Python path
sys.path.append('/home/harveybc/Documents/GitHub/prediction_provider/plugins_feeder')

from technical_indicators import TechnicalIndicatorCalculator

def debug_technical_indicator_output():
    """Debug what the TechnicalIndicatorCalculator actually produces for Stochastic_%D."""
    
    # Load the same data as the test
    d4_path = '/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv'
    normalized_d4 = pd.read_csv(d4_path)
    
    debug_path = '/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json'
    with open(debug_path, 'r') as f:
        debug_data = json.load(f)
    
    min_vals = {}
    max_vals = {}
    for feature, values in debug_data.items():
        min_vals[feature] = values['min']
        max_vals[feature] = values['max']
    
    # Denormalize HLOC exactly like the test
    hloc_columns = ['OPEN', 'HIGH', 'LOW', 'CLOSE']
    denormalized_data = normalized_d4.copy()
    
    for col in hloc_columns:
        if col in min_vals and col in max_vals:
            min_val = min_vals[col]
            max_val = max_vals[col]
            denormalized_data[col] = normalized_d4[col] * (max_val - min_val) + min_val
    
    print(f"Denormalized HLOC data shape: {denormalized_data.shape}")
    print(f"HLOC ranges:")
    for col in hloc_columns:
        values = denormalized_data[col]
        print(f"  {col}: [{values.min():.6f}, {values.max():.6f}]")
    
    # Create the HLOC data for TechnicalIndicatorCalculator exactly like the test
    data = pd.DataFrame({
        'Open': denormalized_data['OPEN'],
        'High': denormalized_data['HIGH'], 
        'Low': denormalized_data['LOW'],
        'Close': denormalized_data['CLOSE']
    })
    
    print(f"\nData for TechnicalIndicatorCalculator:")
    print(f"  Shape: {data.shape}")
    print(f"  Index: {data.index[:5].tolist()}")
    print(f"  Columns: {data.columns.tolist()}")
    
    # Initialize calculator and calculate indicators
    calculator = TechnicalIndicatorCalculator()
    indicators = calculator.calculate_all_indicators(data)
    
    print(f"\nIndicators result:")
    print(f"  Shape: {indicators.shape}")
    print(f"  Columns: {indicators.columns.tolist()}")
    print(f"  Index: {indicators.index[:5].tolist()}")
    
    if 'Stochastic_%D' in indicators.columns:
        stoch_d = indicators['Stochastic_%D']
        print(f"\nStochastic_%D from calculator:")
        print(f"  Range: [{stoch_d.min():.6f}, {stoch_d.max():.6f}]")
        print(f"  First 10: {stoch_d.iloc[:10].tolist()}")
        print(f"  Shape: {stoch_d.shape}")
        print(f"  Data type: {stoch_d.dtype}")
        print(f"  Has NaN: {stoch_d.isna().any()}")
        print(f"  NaN count: {stoch_d.isna().sum()}")
        
        # Now normalize it exactly like the test does
        min_val = min_vals['Stochastic_%D']
        max_val = max_vals['Stochastic_%D']
        
        print(f"\nNormalization parameters for Stochastic_%D:")
        print(f"  min: {min_val}")
        print(f"  max: {max_val}")
        
        # Normalize like the test
        normalized_stoch_d = (stoch_d - min_val) / (max_val - min_val)
        
        print(f"\nNormalized Stochastic_%D:")
        print(f"  Range: [{normalized_stoch_d.min():.6f}, {normalized_stoch_d.max():.6f}]")
        print(f"  First 10: {normalized_stoch_d.iloc[:10].tolist()}")
        
        # Compare with reference (using alignment like the test)
        window_offset = 200
        reference_stoch_d = normalized_d4['Stochastic_%D'].iloc[window_offset:window_offset+1000]
        aligned_normalized = normalized_stoch_d.iloc[window_offset:window_offset+1000]
        
        print(f"\nAligned comparison (window offset {window_offset}):")
        print(f"Reference range: [{reference_stoch_d.min():.6f}, {reference_stoch_d.max():.6f}]")
        print(f"Calculated range: [{aligned_normalized.min():.6f}, {aligned_normalized.max():.6f}]")
        print(f"Reference first 5: {reference_stoch_d.iloc[:5].tolist()}")
        print(f"Calculated first 5: {aligned_normalized.iloc[:5].tolist()}")
        
        # Calculate differences
        diff = np.abs(reference_stoch_d.values - aligned_normalized.values)
        print(f"\nDifferences:")
        print(f"  Max diff: {diff.max():.10f}")
        print(f"  Mean diff: {diff.mean():.10f}")
        print(f"  First 5 diffs: {diff[:5].tolist()}")
        
        # Check for any indexing issues
        print(f"\nIndex debugging:")
        print(f"  Reference indices: {reference_stoch_d.index[:5].tolist()}")
        print(f"  Calculated indices: {aligned_normalized.index[:5].tolist()}")
    else:
        print(f"\nERROR: Stochastic_%D not found in calculated indicators!")
        print(f"Available indicators: {indicators.columns.tolist()}")

if __name__ == "__main__":
    debug_technical_indicator_output()
