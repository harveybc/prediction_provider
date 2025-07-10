#!/usr/bin/env python3
"""
Debug script to check what our technical indicators are returning vs what we expect.
"""

import pandas as pd
import pandas_ta as ta
import numpy as np
from plugins_feeder.technical_indicators import TechnicalIndicatorCalculator
import json

def main():
    print("=== Debug Technical Indicators ===")
    
    # Load a small sample of the d4 data for debugging
    d4_path = 'examples/data/phase_3/normalized_d4.csv'
    normalized_d4 = pd.read_csv(d4_path)
    
    # Load normalization parameters
    debug_path = 'examples/data/phase_3/phase_3_debug_out.json'
    with open(debug_path, 'r') as f:
        debug_data = json.load(f)
    
    # Extract min and max values
    min_vals = {}
    max_vals = {}
    for feature, values in debug_data.items():
        min_vals[feature] = values['min']
        max_vals[feature] = values['max']
    
    # Denormalize OHLC data
    ohlc_cols = ['OPEN', 'HIGH', 'LOW', 'CLOSE']
    denormalized_data = normalized_d4[ohlc_cols].copy()
    
    for col in ohlc_cols:
        if col in min_vals and col in max_vals:
            min_val = min_vals[col]
            max_val = max_vals[col]
            denormalized_data[col] = normalized_d4[col] * (max_val - min_val) + min_val
    
    print(f"Denormalized data shape: {denormalized_data.shape}")
    print(f"Sample denormalized CLOSE: {denormalized_data['CLOSE'].iloc[250:255].values}")
    
    # Calculate indicators using our calculator
    calculator = TechnicalIndicatorCalculator()
    indicators_df = calculator.calculate_all_indicators(denormalized_data.iloc[200:1200])
    
    print(f"\nOur indicators shape: {indicators_df.shape}")
    print(f"Our indicators columns: {indicators_df.columns.tolist()}")
    
    # Check a few specific indicators
    test_indicators = ['MACD', 'MACD_Signal', 'ATR', 'ADX']
    
    for indicator in test_indicators:
        if indicator in indicators_df.columns:
            values = indicators_df[indicator].dropna()
            print(f"\n{indicator}:")
            print(f"  Raw range: [{values.min():.6f}, {values.max():.6f}]")
            print(f"  Sample values: {values.iloc[50:55].values}")
            
            if indicator in min_vals and indicator in max_vals:
                # Normalize using the expected min/max
                min_val = min_vals[indicator] 
                max_val = max_vals[indicator]
                if max_val != min_val:
                    normalized = (values - min_val) / (max_val - min_val)
                    print(f"  Expected min/max: [{min_val:.6f}, {max_val:.6f}]")
                    print(f"  Normalized range: [{normalized.min():.6f}, {normalized.max():.6f}]")
                    print(f"  Normalized sample: {normalized.iloc[50:55].values}")
                    
                    # Compare with actual d4 values
                    if indicator in normalized_d4.columns:
                        d4_values = normalized_d4[indicator].iloc[250:255]  # 200 offset + 50
                        print(f"  D4 sample: {d4_values.values}")
                else:
                    print(f"  ERROR: min == max ({min_val})")
    
    # Test specific MACD calculation to see what columns we get
    print("\n=== Raw MACD Test ===")
    test_close = denormalized_data['CLOSE'].iloc[200:300]
    raw_macd = ta.macd(test_close)
    if raw_macd is not None:
        print(f"Raw MACD columns: {raw_macd.columns.tolist()}")
        for col in raw_macd.columns:
            values = raw_macd[col].dropna()
            if len(values) > 0:
                print(f"  {col}: range [{values.min():.6f}, {values.max():.6f}]")

if __name__ == "__main__":
    main()
