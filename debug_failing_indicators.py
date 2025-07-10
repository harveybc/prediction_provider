#!/usr/bin/env python3
"""
Debug script to understand the exact transformation applied to the 5 failing indicators.
"""

import pandas as pd
import numpy as np
import json
from scipy.stats import skew, kurtosis
import pandas_ta as ta

def load_reference_data():
    """Load the reference normalized data and normalization parameters."""
    # Load normalized data
    normalized_df = pd.read_csv('/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv')
    
    # Load normalization parameters
    with open('/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json', 'r') as f:
        norm_params = json.load(f)
    
    return normalized_df, norm_params

def denormalize_ohlc_data(normalized_df, norm_params):
    """Denormalize OHLC data to get original values."""
    ohlc_columns = ['OPEN', 'HIGH', 'LOW', 'CLOSE']
    denormalized_data = {}
    
    for col in ohlc_columns:
        if col in normalized_df.columns and col in norm_params:
            min_val = norm_params[col]['min']
            max_val = norm_params[col]['max']
            denormalized_data[col] = normalized_df[col] * (max_val - min_val) + min_val
    
    return pd.DataFrame(denormalized_data)

def test_normality_transformation(indicator_name, values):
    """Test the feature-eng normality-based transformation logic."""
    print(f"\n=== Testing {indicator_name} ===")
    
    # Remove NaNs for analysis
    clean_values = values.dropna()
    print(f"Clean values range: [{clean_values.min():.6f}, {clean_values.max():.6f}]")
    
    # Calculate normality score for original data
    skewness_original = skew(clean_values)
    kurtosis_original = kurtosis(clean_values)
    normality_score_original = abs(skewness_original) + abs(kurtosis_original)
    print(f"Original normality score: {normality_score_original:.6f} (skew: {skewness_original:.6f}, kurt: {kurtosis_original:.6f})")
    
    # Prepare data for log transformation
    if (clean_values <= 0).any():
        min_value = clean_values.min()
        shifted_data = clean_values - min_value + 1
        print(f"Shifted data for log (min was {min_value:.6f}): [{shifted_data.min():.6f}, {shifted_data.max():.6f}]")
    else:
        shifted_data = clean_values
        print(f"Data already positive, no shift needed")
    
    # Apply log transformation
    log_transformed_data = np.log(shifted_data)
    
    # Calculate normality score for log-transformed data
    skewness_log = skew(log_transformed_data)
    kurtosis_log = kurtosis(log_transformed_data)
    normality_score_log = abs(skewness_log) + abs(kurtosis_log)
    print(f"Log-transformed normality score: {normality_score_log:.6f} (skew: {skewness_log:.6f}, kurt: {kurtosis_log:.6f})")
    
    # Decision
    if normality_score_log < normality_score_original:
        print(f"→ LOG TRANSFORMATION APPLIED (improved normality)")
        # Apply to full series
        if (values <= 0).any():
            min_value = values.min()
            full_shifted = values - min_value + 1
        else:
            full_shifted = values
        result = np.log(full_shifted.clip(lower=1e-8))
        print(f"Final transformed range: [{result.min():.6f}, {result.max():.6f}]")
        return result, True
    else:
        print(f"→ ORIGINAL DATA USED (log transform did not improve normality)")
        print(f"Final original range: [{values.min():.6f}, {values.max():.6f}]")
        return values, False

def main():
    print("=== Debugging Failing Indicators ===\n")
    
    try:
        # Load data
        print("Loading reference data...")
        normalized_df, norm_params = load_reference_data()
        print(f"Loaded normalized data with shape: {normalized_df.shape}")
        
        print("Denormalizing OHLC data...")
        ohlc_data = denormalize_ohlc_data(normalized_df, norm_params)
        print(f"Denormalized OHLC data with shape: {ohlc_data.shape}")
        
        # Use first 1000 rows + 200 for indicator calculations
        ohlc_subset = ohlc_data.iloc[:1200].copy()
        ohlc_subset.columns = ['Open', 'High', 'Low', 'Close']  # pandas_ta expects this format
        print(f"Using OHLC subset with shape: {ohlc_subset.shape}")
        
        failing_indicators = ['MACD', 'MACD_Signal', 'Stochastic_%D', 'ADX', 'DI+']
        
        print("Expected ranges from phase_3_debug_out.json:")
        for indicator in failing_indicators:
            if indicator in norm_params:
                min_val = norm_params[indicator]['min']
                max_val = norm_params[indicator]['max']
                print(f"{indicator}: [{min_val:.6f}, {max_val:.6f}]")
        
        print("\n" + "="*60)
        
        # Calculate each failing indicator and test transformation
        
        # MACD
        print("\n1. MACD Analysis")
        print("Calculating MACD...")
        macd = ta.macd(ohlc_subset['Close'])
        print(f"MACD columns: {macd.columns.tolist() if macd is not None else 'None'}")
        if macd is not None and 'MACD_12_26_9' in macd.columns:
            raw_macd = macd['MACD_12_26_9']
            print(f"Raw MACD range: [{raw_macd.min():.6f}, {raw_macd.max():.6f}]")
            transformed_macd, used_log = test_normality_transformation('MACD', raw_macd)
            expected_range = [norm_params['MACD']['min'], norm_params['MACD']['max']]
            print(f"Expected after normalization: {expected_range}")
        
        # MACD_Signal
        print("\n2. MACD_Signal Analysis")
        if macd is not None and 'MACDs_12_26_9' in macd.columns:
            raw_macd_signal = macd['MACDs_12_26_9']
            print(f"Raw MACD_Signal range: [{raw_macd_signal.min():.6f}, {raw_macd_signal.max():.6f}]")
            transformed_macd_signal, used_log = test_normality_transformation('MACD_Signal', raw_macd_signal)
            expected_range = [norm_params['MACD_Signal']['min'], norm_params['MACD_Signal']['max']]
            print(f"Expected after normalization: {expected_range}")
        
        # Stochastic_%D
        print("\n3. Stochastic_%D Analysis")
        print("Calculating Stochastic...")
        stoch = ta.stoch(ohlc_subset['High'], ohlc_subset['Low'], ohlc_subset['Close'])
        print(f"Stoch columns: {stoch.columns.tolist() if stoch is not None else 'None'}")
        if stoch is not None and 'STOCHd_14_3_3' in stoch.columns:
            raw_stoch_d = stoch['STOCHd_14_3_3']
            print(f"Raw Stochastic_%D range: [{raw_stoch_d.min():.6f}, {raw_stoch_d.max():.6f}]")
            transformed_stoch_d, used_log = test_normality_transformation('Stochastic_%D', raw_stoch_d)
            expected_range = [norm_params['Stochastic_%D']['min'], norm_params['Stochastic_%D']['max']]
            print(f"Expected after normalization: {expected_range}")
        
        # ADX
        print("\n4. ADX Analysis")
        print("Calculating ADX...")
        adx_data = ta.adx(ohlc_subset['High'], ohlc_subset['Low'], ohlc_subset['Close'])
        print(f"ADX columns: {adx_data.columns.tolist() if adx_data is not None else 'None'}")
        if adx_data is not None and 'ADX_14' in adx_data.columns:
            raw_adx = adx_data['ADX_14']
            print(f"Raw ADX range: [{raw_adx.min():.6f}, {raw_adx.max():.6f}]")
            transformed_adx, used_log = test_normality_transformation('ADX', raw_adx)
            expected_range = [norm_params['ADX']['min'], norm_params['ADX']['max']]
            print(f"Expected after normalization: {expected_range}")
        
        # DI+
        print("\n5. DI+ Analysis")
        if adx_data is not None and 'DMP_14' in adx_data.columns:
            raw_di_plus = adx_data['DMP_14']
            print(f"Raw DI+ range: [{raw_di_plus.min():.6f}, {raw_di_plus.max():.6f}]")
            transformed_di_plus, used_log = test_normality_transformation('DI+', raw_di_plus)
            expected_range = [norm_params['DI+']['min'], norm_params['DI+']['max']]
            print(f"Expected after normalization: {expected_range}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
