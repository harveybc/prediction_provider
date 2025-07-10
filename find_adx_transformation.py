#!/usr/bin/env python3
"""
Investigate the transformation needed to make our ADX values exactly match
the reference Stochastic_%D values.
"""

import pandas as pd
import numpy as np
import json
import sys

# Add the plugins_feeder directory to the Python path
sys.path.append('/home/harveybc/Documents/GitHub/prediction_provider/plugins_feeder')

from technical_indicators import TechnicalIndicatorCalculator

def load_data():
    """Load the test data."""
    # Load normalized training data
    d4_path = '/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv'
    normalized_d4 = pd.read_csv(d4_path)
    
    # Load normalization parameters
    debug_path = '/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json'
    with open(debug_path, 'r') as f:
        debug_data = json.load(f)
    
    min_vals = {}
    max_vals = {}
    for feature, values in debug_data.items():
        min_vals[feature] = values['min']
        max_vals[feature] = values['max']
    
    return normalized_d4, min_vals, max_vals

def denormalize_ohlc(normalized_d4, min_vals, max_vals):
    """Denormalize OHLC columns."""
    denormalized_data = pd.DataFrame()
    
    for col in ['OPEN', 'HIGH', 'LOW', 'CLOSE']:
        if col in normalized_d4.columns:
            min_val = min_vals[col]
            max_val = max_vals[col]
            denormalized_data[col] = normalized_d4[col] * (max_val - min_val) + min_val
            
    return denormalized_data

def find_adx_transformation():
    """Find the exact transformation to make our ADX match reference Stochastic_%D."""
    print("=== Finding ADX to Stochastic_%D Transformation ===\n")
    
    # Load data
    normalized_d4, min_vals, max_vals = load_data()
    ohlc_data = denormalize_ohlc(normalized_d4, min_vals, max_vals)
    
    # Calculate our indicators
    calculator = TechnicalIndicatorCalculator()
    indicators = calculator.calculate_all_indicators(ohlc_data)
    
    # Get our ADX values
    our_adx = indicators['ADX'].dropna()
    print(f"Our ADX range: [{our_adx.min():.6f}, {our_adx.max():.6f}]")
    
    # Get reference Stochastic_%D values (denormalized)
    ref_stoch_d_normalized = normalized_d4['Stochastic_%D']
    min_val = min_vals['Stochastic_%D']
    max_val = max_vals['Stochastic_%D']
    ref_stoch_d_denormalized = ref_stoch_d_normalized * (max_val - min_val) + min_val
    
    print(f"Reference Stochastic_%D range: [{ref_stoch_d_denormalized.min():.6f}, {ref_stoch_d_denormalized.max():.6f}]")
    
    # Align the data
    first_valid_idx = indicators['ADX'].first_valid_index()
    if first_valid_idx is not None:
        offset = indicators['ADX'].index.get_loc(first_valid_idx)
        
        # Use first 1000 values for analysis
        our_adx_values = our_adx.head(1000).values
        ref_stoch_d_values = ref_stoch_d_denormalized.iloc[offset:offset + len(our_adx_values)].values
        
        min_length = min(len(our_adx_values), len(ref_stoch_d_values))
        our_adx_values = our_adx_values[:min_length]
        ref_stoch_d_values = ref_stoch_d_values[:min_length]
        
        print(f"Aligned data length: {min_length}")
        print(f"Our ADX first 10: {our_adx_values[:10]}")
        print(f"Ref Stochastic_%D first 10: {ref_stoch_d_values[:10]}")
        
        # Try linear transformation: ref = a * our + b
        print(f"\n=== Linear Transformation Analysis ===")
        try:
            A = np.vstack([our_adx_values, np.ones(len(our_adx_values))]).T
            coeffs, residuals, rank, s = np.linalg.lstsq(A, ref_stoch_d_values, rcond=None)
            a, b = coeffs
            
            print(f"Linear fit: ref = {a:.6f} * our_adx + {b:.6f}")
            
            # Test the transformation
            our_transformed = a * our_adx_values + b
            max_diff = np.abs(our_transformed - ref_stoch_d_values).max()
            mean_diff = np.abs(our_transformed - ref_stoch_d_values).mean()
            
            print(f"After linear transformation:")
            print(f"  Max difference: {max_diff:.6f}")
            print(f"  Mean difference: {mean_diff:.6f}")
            
            if max_diff < 0.01:
                print(f"🎉 PERFECT LINEAR TRANSFORMATION FOUND!")
                print(f"Formula: stochastic_d = {a:.6f} * adx + {b:.6f}")
                return a, b, 'linear'
            elif max_diff < 0.1:
                print(f"✅ Good linear transformation found!")
                print(f"Formula: stochastic_d = {a:.6f} * adx + {b:.6f}")
                
                # Show some examples
                print(f"\nExamples:")
                for i in range(min(5, len(our_adx_values))):
                    original = our_adx_values[i]
                    transformed = our_transformed[i]
                    reference = ref_stoch_d_values[i]
                    error = abs(transformed - reference)
                    print(f"  ADX: {original:.6f} -> Transformed: {transformed:.6f}, Reference: {reference:.6f}, Error: {error:.6f}")
                
                return a, b, 'linear'
        except Exception as e:
            print(f"Linear transformation failed: {e}")
        
        # Try ratio-based scaling
        print(f"\n=== Ratio-based Scaling Analysis ===")
        mask = our_adx_values != 0
        if mask.sum() > 100:
            ratios = ref_stoch_d_values[mask] / our_adx_values[mask]
            ratio_mean = ratios.mean()
            ratio_std = ratios.std()
            
            print(f"Ratio statistics:")
            print(f"  Mean ratio: {ratio_mean:.6f}")
            print(f"  Std ratio: {ratio_std:.6f}")
            
            if ratio_std < 0.1:
                our_ratio_transformed = our_adx_values * ratio_mean
                max_diff = np.abs(our_ratio_transformed - ref_stoch_d_values).max()
                mean_diff = np.abs(our_ratio_transformed - ref_stoch_d_values).mean()
                
                print(f"After ratio transformation (multiply by {ratio_mean:.6f}):")
                print(f"  Max difference: {max_diff:.6f}")
                print(f"  Mean difference: {mean_diff:.6f}")
                
                if max_diff < 0.01:
                    print(f"🎉 PERFECT RATIO TRANSFORMATION FOUND!")
                    print(f"Formula: stochastic_d = adx * {ratio_mean:.6f}")
                    return ratio_mean, 0, 'ratio'
        
        # Try more complex transformations
        print(f"\n=== Advanced Transformation Analysis ===")
        
        # Try polynomial fit (degree 2)
        try:
            coeffs = np.polyfit(our_adx_values, ref_stoch_d_values, 2)
            a, b, c = coeffs
            
            our_poly_transformed = a * our_adx_values**2 + b * our_adx_values + c
            max_diff = np.abs(our_poly_transformed - ref_stoch_d_values).max()
            mean_diff = np.abs(our_poly_transformed - ref_stoch_d_values).mean()
            
            print(f"Polynomial fit (degree 2): ref = {a:.6f} * adx^2 + {b:.6f} * adx + {c:.6f}")
            print(f"  Max difference: {max_diff:.6f}")
            print(f"  Mean difference: {mean_diff:.6f}")
            
            if max_diff < 0.01:
                print(f"🎉 PERFECT POLYNOMIAL TRANSFORMATION FOUND!")
                return (a, b, c), 0, 'polynomial'
        except Exception as e:
            print(f"Polynomial transformation failed: {e}")
        
        # Try exponential/logarithmic relationships
        try:
            # Test: ref = a * exp(b * adx)
            from scipy.optimize import curve_fit
            
            def exp_func(x, a, b):
                return a * np.exp(b * x)
            
            popt, pcov = curve_fit(exp_func, our_adx_values, ref_stoch_d_values, maxfev=5000)
            a_exp, b_exp = popt
            
            our_exp_transformed = exp_func(our_adx_values, a_exp, b_exp)
            max_diff = np.abs(our_exp_transformed - ref_stoch_d_values).max()
            mean_diff = np.abs(our_exp_transformed - ref_stoch_d_values).mean()
            
            print(f"Exponential fit: ref = {a_exp:.6f} * exp({b_exp:.6f} * adx)")
            print(f"  Max difference: {max_diff:.6f}")
            print(f"  Mean difference: {mean_diff:.6f}")
            
            if max_diff < 0.01:
                print(f"🎉 PERFECT EXPONENTIAL TRANSFORMATION FOUND!")
                return (a_exp, b_exp), 0, 'exponential'
        except Exception as e:
            print(f"Exponential transformation failed: {e}")
    
    return None, None, None

if __name__ == '__main__':
    find_adx_transformation()
