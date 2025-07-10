#!/usr/bin/env python3
"""
Reverse engineer the exact pre-normalization values from normalized_d4.csv
to understand what transformations were applied.
"""

import pandas as pd
import numpy as np
import json

def main():
    print("=== Reverse Engineering Pre-Normalization Values ===\n")
    
    # Load data
    normalized_df = pd.read_csv('/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv')
    
    with open('/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json', 'r') as f:
        norm_params = json.load(f)
    
    failing_indicators = ['MACD', 'MACD_Signal', 'Stochastic_%D', 'ADX', 'DI+']
    
    print("Reverse engineering pre-normalization values for first 10 rows:\n")
    
    for indicator in failing_indicators:
        if indicator in normalized_df.columns and indicator in norm_params:
            min_val = norm_params[indicator]['min']
            max_val = norm_params[indicator]['max']
            
            # Denormalize first 10 values
            normalized_values = normalized_df[indicator].iloc[:10]
            denormalized_values = normalized_values * (max_val - min_val) + min_val
            
            print(f"{indicator}:")
            print(f"  Normalization range: [{min_val:.6f}, {max_val:.6f}]")
            print(f"  First 10 normalized values: {normalized_values.values}")
            print(f"  First 10 denormalized values: {denormalized_values.values}")
            print(f"  Denormalized range in sample: [{denormalized_values.min():.6f}, {denormalized_values.max():.6f}]")
            print()

if __name__ == "__main__":
    main()
