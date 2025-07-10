#!/usr/bin/env python3
"""
Debug the specific indicators that are failing validation.
"""

import pandas as pd
import pandas_ta as ta
import numpy as np
import json

def main():
    try:
        print("=== Debug Failed Indicators ===")
        
        # Load test data
        d4_path = 'examples/data/phase_3/normalized_d4.csv'
        normalized_d4 = pd.read_csv(d4_path)
        print(f"Loaded d4 data with shape: {normalized_d4.shape}")
        
        debug_path = 'examples/data/phase_3/phase_3_debug_out.json'
        with open(debug_path, 'r') as f:
            debug_data = json.load(f)
        print(f"Loaded debug data with {len(debug_data)} indicators")
    
    # Extract min and max values
    min_vals = {}
    max_vals = {}
    for feature, values in debug_data.items():
        min_vals[feature] = values['min']
        max_vals[feature] = values['max']
    
    # Denormalize OHLC data - use a larger range to analyze patterns
    test_range = slice(200, 1200)
    ohlc_cols = ['OPEN', 'HIGH', 'LOW', 'CLOSE']
    denormalized_data = pd.DataFrame(index=normalized_d4.index[test_range])
    
    for col in ohlc_cols:
        min_val = min_vals[col]
        max_val = max_vals[col]
        denormalized_data[col] = normalized_d4[col].iloc[test_range] * (max_val - min_val) + min_val
    
    # Prepare for pandas_ta
    ohlc_data = denormalized_data.copy()
    ohlc_data.columns = ['Open', 'High', 'Low', 'Close']
    
    # Debug specific failing indicators
    failing_indicators = ['MACD', 'MACD_Signal', 'Stochastic_%D', 'ADX', 'EMA']
    
    for indicator in failing_indicators:
        print(f"\n=== {indicator} Analysis ===")
        
        # Get expected values from d4
        if indicator in normalized_d4.columns:
            min_val = min_vals[indicator]
            max_val = max_vals[indicator]
            d4_normalized = normalized_d4[indicator].iloc[test_range]
            d4_denormalized = d4_normalized * (max_val - min_val) + min_val
            
            print(f"D4 {indicator} (denormalized): range [{d4_denormalized.min():.6f}, {d4_denormalized.max():.6f}]")
            print(f"D4 {indicator} first 5 values: {d4_denormalized.iloc[:5].values}")
            
            # Calculate using our method
            if indicator == 'MACD':
                our_result = ta.macd(ohlc_data['Close'])
                if our_result is not None and 'MACD_12_26_9' in our_result.columns:
                    our_values = np.maximum(our_result['MACD_12_26_9'], 0).dropna()
                    print(f"Our {indicator}: range [{our_values.min():.6f}, {our_values.max():.6f}]")
                    print(f"Our {indicator} first 5 values: {our_values.iloc[:5].values}")
                    
                    # Check different transformations
                    original_macd = our_result['MACD_12_26_9'].dropna()
                    print(f"Original MACD (before clipping): range [{original_macd.min():.6f}, {original_macd.max():.6f}]")
                    
                    # Try absolute values
                    abs_macd = np.abs(original_macd)
                    print(f"Absolute MACD: range [{abs_macd.min():.6f}, {abs_macd.max():.6f}]")
                    
            elif indicator == 'MACD_Signal':
                our_result = ta.macd(ohlc_data['Close'])
                if our_result is not None and 'MACDs_12_26_9' in our_result.columns:
                    our_values = np.maximum(our_result['MACDs_12_26_9'], 0).dropna()
                    print(f"Our {indicator}: range [{our_values.min():.6f}, {our_values.max():.6f}]")
                    
                    # Check original before clipping
                    original_signal = our_result['MACDs_12_26_9'].dropna()
                    print(f"Original MACD_Signal (before clipping): range [{original_signal.min():.6f}, {original_signal.max():.6f}]")
                    
                    # Try absolute values
                    abs_signal = np.abs(original_signal)
                    print(f"Absolute MACD_Signal: range [{abs_signal.min():.6f}, {abs_signal.max():.6f}]")
                    
            elif indicator == 'Stochastic_%D':
                our_result = ta.stoch(ohlc_data['High'], ohlc_data['Low'], ohlc_data['Close'])
                if our_result is not None and 'STOCHd_14_3_3' in our_result.columns:
                    our_values = our_result['STOCHd_14_3_3'].dropna()
                    print(f"Our {indicator}: range [{our_values.min():.6f}, {our_values.max():.6f}]")
                    print(f"Our {indicator} first 5 values: {our_values.iloc[:5].values}")
                    
                    # The expected range suggests it might be normalized differently
                    # D4 range: [-0.0669014846425095, 4.597806251789268]
                    # Our range is much higher, suggesting different calculation
                    
                    # Try different stochastic parameters
                    stoch_alt = ta.stoch(ohlc_data['High'], ohlc_data['Low'], ohlc_data['Close'], k=14, d=3, smooth_k=1)
                    if stoch_alt is not None:
                        print(f"Alternative stoch columns: {stoch_alt.columns.tolist()}")
                    
            elif indicator == 'ADX':
                our_result = ta.adx(ohlc_data['High'], ohlc_data['Low'], ohlc_data['Close'], length=14)
                if our_result is not None and 'ADX_14' in our_result.columns:
                    our_values = our_result['ADX_14'].dropna()
                    print(f"Our {indicator}: range [{our_values.min():.6f}, {our_values.max():.6f}]")
                    print(f"Our {indicator} first 5 values: {our_values.iloc[:5].values}")
                    
                    # Expected range: [1.777476, 4.319690] - much smaller than our values
                    # This suggests log transformation or different calculation
                    our_log = np.log(our_values)
                    print(f"Log(ADX): range [{our_log.min():.6f}, {our_log.max():.6f}]")
                    
            elif indicator == 'EMA':
                our_result = ta.ema(ohlc_data['Close'], length=20)
                if our_result is not None:
                    our_values = our_result.dropna()
                    print(f"Our {indicator}: range [{our_values.min():.6f}, {our_values.max():.6f}]")
                    print(f"Our {indicator} first 5 values: {our_values.iloc[:5].values}")
                    
                    # Small difference - might be rounding or slight parameter difference

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
