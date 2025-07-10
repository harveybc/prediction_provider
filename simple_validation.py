#!/usr/bin/env python3
"""
Simple validation test to check if our indicators match expected patterns.
"""

try:
    import pandas as pd
    import numpy as np
    import json
    
    # Load data  
    normalized_d4 = pd.read_csv('/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv')
    
    with open('/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json', 'r') as f:
        debug_data = json.load(f)
    
    # Test a small calculation
    from plugins_feeder.technical_indicators import TechnicalIndicatorCalculator
    
    # Extract min/max
    min_vals = {k: v['min'] for k, v in debug_data.items()}
    max_vals = {k: v['max'] for k, v in debug_data.items()}
    
    # Denormalize a small sample
    test_range = slice(400, 500)  # 100 rows for quick test
    ohlc_cols = ['OPEN', 'HIGH', 'LOW', 'CLOSE']
    denormalized = pd.DataFrame()
    
    for col in ohlc_cols:
        min_val = min_vals[col]
        max_val = max_vals[col]
        denormalized[col] = normalized_d4[col].iloc[test_range] * (max_val - min_val) + min_val
    
    # Calculate indicators
    calculator = TechnicalIndicatorCalculator()
    indicators = calculator.calculate_all_indicators(denormalized)
    
    # Check key indicators
    test_indicators = ['RSI', 'MACD', 'ADX', 'ATR', 'Stochastic_%D']
    
    print("=== Indicator Validation ===")
    for indicator in test_indicators:
        if indicator in indicators.columns:
            values = indicators[indicator].dropna()
            if len(values) > 0:
                print(f"{indicator}: range [{values.min():.6f}, {values.max():.6f}]")
                
                # Compare with expected (denormalized) values
                if indicator in min_vals and indicator in max_vals:
                    expected_min = min_vals[indicator]
                    expected_max = max_vals[indicator]
                    
                    # Normalize our values using expected range
                    if expected_max != expected_min:
                        normalized_ours = (values - expected_min) / (expected_max - expected_min)
                        d4_sample = normalized_d4[indicator].iloc[test_range].dropna()
                        
                        if len(normalized_ours) > 0 and len(d4_sample) > 0:
                            # Compare first few values
                            min_len = min(len(normalized_ours), len(d4_sample), 5)
                            our_sample = normalized_ours.iloc[:min_len].values
                            d4_sample_vals = d4_sample.iloc[:min_len].values
                            
                            diff = np.abs(our_sample - d4_sample_vals).max()
                            match = diff < 0.001
                            print(f"  Match: {match} (max diff: {diff:.6f})")
                            if not match:
                                print(f"  Our:  {our_sample}")
                                print(f"  D4:   {d4_sample_vals}")
            else:
                print(f"{indicator}: No values calculated")
        else:
            print(f"{indicator}: Not in calculated indicators")
    
    print("\nSuccess!")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
