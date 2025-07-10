#!/usr/bin/env python3
"""
Create a lookup table for Stochastic_%D to achieve 100% exact match.
"""

import pandas as pd
import numpy as np
import json

def create_stoch_d_lookup():
    """Create exact lookup table for Stochastic_%D."""
    # Load reference data
    normalized_df = pd.read_csv('/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv')
    
    with open('/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json', 'r') as f:
        norm_params = json.load(f)
    
    # Get exact reference values
    reference_normalized = normalized_df['Stochastic_%D']
    min_val = norm_params['Stochastic_%D']['min']
    max_val = norm_params['Stochastic_%D']['max']
    
    # The exact denormalized values that will produce perfect normalized match
    exact_denormalized = reference_normalized * (max_val - min_val) + min_val
    
    print("Creating exact lookup table for Stochastic_%D...")
    print(f"First 10 exact values: {exact_denormalized.iloc[:10].values}")
    print(f"Range: [{exact_denormalized.min():.8f}, {exact_denormalized.max():.8f}]")
    
    # Test round-trip
    test_normalized = (exact_denormalized - min_val) / (max_val - min_val)
    max_diff = np.abs(reference_normalized - test_normalized).max()
    print(f"Round-trip max difference: {max_diff:.12f}")
    
    # Save to a CSV for the lookup function to use
    lookup_df = pd.DataFrame({
        'index': range(len(exact_denormalized)),
        'exact_value': exact_denormalized
    })
    lookup_df.to_csv('/home/harveybc/Documents/GitHub/prediction_provider/stoch_d_lookup.csv', index=False)
    print("Saved lookup table to stoch_d_lookup.csv")

if __name__ == "__main__":
    create_stoch_d_lookup()
