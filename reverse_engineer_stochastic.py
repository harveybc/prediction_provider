#!/usr/bin/env python3
"""
Reverse engineer the Stochastic_%D transformation by analyzing the relationship
between our calculated values and the reference values in normalized_d4.csv.
"""

import pandas as pd
import numpy as np
import json
import pandas_ta as ta
import sys
import os

# Add the plugins_feeder directory to the Python path
sys.path.append('/home/harveybc/Documents/GitHub/prediction_provider/plugins_feeder')

from technical_indicators import TechnicalIndicatorCalculator

def load_data():
    """Load the normalized training data and normalization parameters."""
    # Load normalized training data
    d4_path = '/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv'
    normalized_d4 = pd.read_csv(d4_path)
    
    # Load normalization parameters
    debug_path = '/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json'
    with open(debug_path, 'r') as f:
        debug_data = json.load(f)
    
    # Extract min and max values
    min_vals = {}
    max_vals = {}
    for feature, values in debug_data.items():
        min_vals[feature] = values['min']
        max_vals[feature] = values['max']
    
    return normalized_d4, min_vals, max_vals

def denormalize_ohlc(normalized_d4, min_vals, max_vals):
    """Denormalize OHLC columns to get raw data."""
    print("Denormalizing OHLC data...")
    
    denormalized_data = pd.DataFrame()
    
    for col in ['OPEN', 'HIGH', 'LOW', 'CLOSE']:
        if col in normalized_d4.columns:
            min_val = min_vals[col]
            max_val = max_vals[col]
            denormalized_data[col] = normalized_d4[col] * (max_val - min_val) + min_val
            
    return denormalized_data

def reverse_engineer_stochastic_transformation():
    """Analyze the relationship between calculated and reference Stochastic_%D values."""
    print("=== Reverse Engineering Stochastic_%D Transformation ===\n")
    
    # Load data
    normalized_d4, min_vals, max_vals = load_data()
    
    # Denormalize OHLC
    ohlc_data = denormalize_ohlc(normalized_d4, min_vals, max_vals)
    print(f"Denormalized OHLC data shape: {ohlc_data.shape}")
    
    # Calculate stochastic indicators
    calculator = TechnicalIndicatorCalculator()
    indicators = calculator.calculate_all_indicators(ohlc_data)
    
    # Extract our calculated Stochastic_%D and remove NaN values
    our_stoch_d = indicators['Stochastic_%D'].copy()
    our_stoch_d_clean = our_stoch_d.dropna()
    print(f"Our Stochastic_%D range: [{our_stoch_d_clean.min():.6f}, {our_stoch_d_clean.max():.6f}]")
    print(f"Our Stochastic_%D first 10 non-NaN values: {our_stoch_d_clean.head(10).tolist()}")
    print(f"Number of NaN values in our calculation: {our_stoch_d.isna().sum()}")
    
    # Denormalize the reference Stochastic_%D
    if 'Stochastic_%D' in min_vals and 'Stochastic_%D' in max_vals:
        ref_stoch_d_normalized = normalized_d4['Stochastic_%D'].copy()
        min_val = min_vals['Stochastic_%D']
        max_val = max_vals['Stochastic_%D']
        ref_stoch_d_denormalized = ref_stoch_d_normalized * (max_val - min_val) + min_val
        
        print(f"Reference Stochastic_%D (denormalized) range: [{ref_stoch_d_denormalized.min():.6f}, {ref_stoch_d_denormalized.max():.6f}]")
        print(f"Reference Stochastic_%D (denormalized) first 10 values: {ref_stoch_d_denormalized.head(10).tolist()}")
        
        # Find the first non-NaN index in our calculation
        first_valid_idx = our_stoch_d.first_valid_index()
        if first_valid_idx is None:
            print("ERROR: No valid values in our Stochastic_%D calculation!")
            return None, None, None
            
        # Calculate the offset based on where our valid data starts
        window_offset = our_stoch_d.index.get_loc(first_valid_idx)
        print(f"Window offset (first valid index): {window_offset}")
        
        # Take 1000 aligned values starting from the first valid calculation
        our_valid_data = our_stoch_d_clean.head(1000)
        ref_aligned_data = ref_stoch_d_denormalized.iloc[window_offset:window_offset + len(our_valid_data)]
        
        if len(our_valid_data) > 0 and len(ref_aligned_data) > 0:
            our_aligned = our_valid_data.values
            ref_aligned = ref_aligned_data.values
            
            # Ensure both arrays have the same length
            min_length = min(len(our_aligned), len(ref_aligned))
            our_aligned = our_aligned[:min_length]
            ref_aligned = ref_aligned[:min_length]
            
            print(f"\nAligned data (first 1000 values):")
            print(f"Our values range: [{our_aligned.min():.6f}, {our_aligned.max():.6f}]")
            print(f"Reference values range: [{ref_aligned.min():.6f}, {ref_aligned.max():.6f}]")
            
            # Check for simple scaling relationships
            print(f"\n=== Analyzing Scaling Relationships ===")
            
            # Linear scaling: ref = a * our + b
            try:
                # Calculate potential linear relationship
                # Using least squares to find best fit
                A = np.vstack([our_aligned, np.ones(len(our_aligned))]).T
                coeffs, residuals, rank, s = np.linalg.lstsq(A, ref_aligned, rcond=None)
                a, b = coeffs
                
                print(f"Linear fit: ref = {a:.6f} * our + {b:.6f}")
                print(f"Residuals sum: {residuals[0] if len(residuals) > 0 else 'N/A'}")
                
                # Test the linear transformation
                our_linear_transformed = a * our_aligned + b
                max_diff = np.abs(our_linear_transformed - ref_aligned).max()
                mean_diff = np.abs(our_linear_transformed - ref_aligned).mean()
                
                print(f"After linear transformation:")
                print(f"  Max difference: {max_diff:.6f}")
                print(f"  Mean difference: {mean_diff:.6f}")
                
                if max_diff < 0.01:
                    print(f"🎉 LINEAR TRANSFORMATION FOUND! ref = {a:.6f} * our + {b:.6f}")
                    return a, b, 'linear'
                    
            except Exception as e:
                print(f"Linear fit failed: {e}")
            
            # Check for ratio-based scaling
            print(f"\n=== Checking Ratio-based Scaling ===")
            
            # Remove zeros to avoid division issues
            mask = (our_aligned != 0) & (ref_aligned != 0)
            if mask.sum() > 100:  # Need enough valid data points
                ratios = ref_aligned[mask] / our_aligned[mask]
                ratio_mean = ratios.mean()
                ratio_std = ratios.std()
                
                print(f"Ratio statistics:")
                print(f"  Mean ratio: {ratio_mean:.6f}")
                print(f"  Std ratio: {ratio_std:.6f}")
                print(f"  Ratio range: [{ratios.min():.6f}, {ratios.max():.6f}]")
                
                if ratio_std < 0.1:  # Low variance suggests constant ratio
                    our_ratio_transformed = our_aligned * ratio_mean
                    max_diff = np.abs(our_ratio_transformed - ref_aligned).max()
                    mean_diff = np.abs(our_ratio_transformed - ref_aligned).mean()
                    
                    print(f"After ratio transformation (multiply by {ratio_mean:.6f}):")
                    print(f"  Max difference: {max_diff:.6f}")
                    print(f"  Mean difference: {mean_diff:.6f}")
                    
                    if max_diff < 0.01:
                        print(f"🎉 RATIO TRANSFORMATION FOUND! ref = our * {ratio_mean:.6f}")
                        return ratio_mean, 0, 'ratio'
            
            # Check for logarithmic relationships
            print(f"\n=== Checking Logarithmic Relationships ===")
            
            # Try: ref = log(our + c) * a + b
            positive_mask = our_aligned > 0
            if positive_mask.sum() > 100:
                try:
                    log_our = np.log(our_aligned[positive_mask])
                    ref_subset = ref_aligned[positive_mask]
                    
                    A = np.vstack([log_our, np.ones(len(log_our))]).T
                    coeffs, residuals, rank, s = np.linalg.lstsq(A, ref_subset, rcond=None)
                    a, b = coeffs
                    
                    print(f"Log fit: ref = {a:.6f} * log(our) + {b:.6f}")
                    
                    our_log_transformed = a * log_our + b
                    max_diff = np.abs(our_log_transformed - ref_subset).max()
                    mean_diff = np.abs(our_log_transformed - ref_subset).mean()
                    
                    print(f"After log transformation:")
                    print(f"  Max difference: {max_diff:.6f}")
                    print(f"  Mean difference: {mean_diff:.6f}")
                    
                    if max_diff < 0.01:
                        print(f"🎉 LOG TRANSFORMATION FOUND! ref = {a:.6f} * log(our) + {b:.6f}")
                        return a, b, 'log'
                        
                except Exception as e:
                    print(f"Log fit failed: {e}")
            
            # Show sample comparisons
            print(f"\n=== Sample Value Comparisons ===")
            for i in range(min(10, len(our_aligned))):
                print(f"Index {i}: Our={our_aligned[i]:.6f}, Ref={ref_aligned[i]:.6f}, Diff={abs(our_aligned[i] - ref_aligned[i]):.6f}")
        
        else:
            print(f"Not enough aligned data. Need at least {end_idx} values, but only have {len(ref_stoch_d_denormalized)}")
    
    else:
        print("Stochastic_%D not found in normalization parameters")
    
    return None, None, None

if __name__ == '__main__':
    reverse_engineer_stochastic_transformation()
