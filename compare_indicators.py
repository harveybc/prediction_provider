#!/usr/bin/env python3
"""
Compare our indicators with the d4 data to understand the mismatch.
"""

import pandas as pd
import pandas_ta as ta
import numpy as np
import json

def main():
    print("=== Comparing Indicator Values ===")
    
    # Load the d4 data and normalization parameters
    d4_path = 'examples/data/phase_3/normalized_d4.csv'
    normalized_d4 = pd.read_csv(d4_path)
    
    debug_path = 'examples/data/phase_3/phase_3_debug_out.json'
    with open(debug_path, 'r') as f:
        debug_data = json.load(f)
    
    # Extract min and max values
    min_vals = {}
    max_vals = {}
    for feature, values in debug_data.items():
        min_vals[feature] = values['min']
        max_vals[feature] = values['max']
    
    # Denormalize a specific range of data to match what we're calculating
    test_range = slice(200, 1200)  # 1000 rows starting from row 200
    
    # Denormalize OHLC data
    ohlc_cols = ['OPEN', 'HIGH', 'LOW', 'CLOSE']
    denormalized_data = pd.DataFrame(index=normalized_d4.index[test_range])
    
    for col in ohlc_cols:
        min_val = min_vals[col]
        max_val = max_vals[col]
        denormalized_data[col] = normalized_d4[col].iloc[test_range] * (max_val - min_val) + min_val
    
    print(f"Denormalized data range: {denormalized_data.index[0]} to {denormalized_data.index[-1]}")
    print(f"Denormalized CLOSE sample: {denormalized_data['CLOSE'].iloc[400:405].values}")
    
    # Denormalize MACD from d4 data for comparison
    macd_col = 'MACD'
    min_val = min_vals[macd_col]
    max_val = max_vals[macd_col]
    d4_macd_normalized = normalized_d4[macd_col].iloc[test_range]
    d4_macd_denormalized = d4_macd_normalized * (max_val - min_val) + min_val
    
    print(f"\nD4 MACD (normalized): range [{d4_macd_normalized.min():.6f}, {d4_macd_normalized.max():.6f}]")
    print(f"D4 MACD (denormalized): range [{d4_macd_denormalized.min():.6f}, {d4_macd_denormalized.max():.6f}]")
    print(f"D4 MACD sample (denormalized): {d4_macd_denormalized.iloc[400:405].values}")
    
    # Calculate MACD using our method
    ohlc_data = denormalized_data.copy()
    ohlc_data.columns = ['Open', 'High', 'Low', 'Close']  # pandas_ta naming
    
    our_macd = ta.macd(ohlc_data['Close'])
    if our_macd is not None and 'MACD_12_26_9' in our_macd.columns:
        our_macd_values = our_macd['MACD_12_26_9'].dropna()
        print(f"\nOur MACD: range [{our_macd_values.min():.6f}, {our_macd_values.max():.6f}]")
        print(f"Our MACD sample: {our_macd_values.iloc[400:405].values}")
        
        # Check if there's a consistent scaling factor
        if len(our_macd_values) > 0 and len(d4_macd_denormalized) > 0:
            # Align indices
            common_idx = our_macd_values.index.intersection(d4_macd_denormalized.index)
            if len(common_idx) > 10:
                our_aligned = our_macd_values.loc[common_idx]
                d4_aligned = d4_macd_denormalized.loc[common_idx]
                
                # Check for scaling factor
                non_zero_mask = (our_aligned != 0) & (d4_aligned != 0)
                if non_zero_mask.sum() > 0:
                    ratios = d4_aligned[non_zero_mask] / our_aligned[non_zero_mask]
                    print(f"\nScaling ratio stats:")
                    print(f"  Mean ratio: {ratios.mean():.6f}")
                    print(f"  Std ratio: {ratios.std():.6f}")
                    print(f"  Min/Max ratio: [{ratios.min():.6f}, {ratios.max():.6f}]")
    
    # Check for any obvious issues with the data
    print(f"\nData quality checks:")
    print(f"  NaN values in OHLC: {denormalized_data.isnull().sum().sum()}")
    print(f"  Any negative prices: {(denormalized_data < 0).sum().sum()}")
    print(f"  CLOSE range: [{denormalized_data['CLOSE'].min():.6f}, {denormalized_data['CLOSE'].max():.6f}]")
    
    # Also check ATR to see the log transformation theory
    print(f"\n=== ATR Analysis ===")
    atr_col = 'ATR'
    min_val = min_vals[atr_col]
    max_val = max_vals[atr_col]
    d4_atr_normalized = normalized_d4[atr_col].iloc[test_range]
    d4_atr_denormalized = d4_atr_normalized * (max_val - min_val) + min_val
    
    print(f"D4 ATR (normalized): range [{d4_atr_normalized.min():.6f}, {d4_atr_normalized.max():.6f}]")
    print(f"D4 ATR (denormalized): range [{d4_atr_denormalized.min():.6f}, {d4_atr_denormalized.max():.6f}]")
    
    # Calculate ATR using our method
    our_atr = ta.atr(ohlc_data['High'], ohlc_data['Low'], ohlc_data['Close'])
    if our_atr is not None:
        our_atr_values = our_atr.dropna()
        print(f"Our ATR: range [{our_atr_values.min():.6f}, {our_atr_values.max():.6f}]")
        
        # Check if log transformation explains the difference
        if len(our_atr_values) > 0:
            our_atr_log = np.log(our_atr_values)
            print(f"Our ATR (log): range [{our_atr_log.min():.6f}, {our_atr_log.max():.6f}]")
            
            # The d4 range is [-7.805674, -4.574163] - this matches log(very small values)!
            print(f"ATR log range matches d4 range: {abs(our_atr_log.min() - min_val) < 1.0}")

if __name__ == "__main__":
    main()
