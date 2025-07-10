#!/usr/bin/env python3
"""
Simple debug script to understand failing indicators.
"""

import pandas as pd
import numpy as np
import json

def main():
    print("=== Simple Debug Start ===")
    
    try:
        # Load normalization parameters
        print("Loading normalization parameters...")
        with open('/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json', 'r') as f:
            norm_params = json.load(f)
        
        failing_indicators = ['MACD', 'MACD_Signal', 'Stochastic_%D', 'ADX', 'DI+']
        
        print("\nExpected ranges from phase_3_debug_out.json:")
        for indicator in failing_indicators:
            if indicator in norm_params:
                min_val = norm_params[indicator]['min']
                max_val = norm_params[indicator]['max']
                print(f"{indicator}: [{min_val:.6f}, {max_val:.6f}]")
        
        print("\nKey observations:")
        print("- MACD min=0.0 → suggests log transformation applied")
        print("- MACD_Signal min=0.0 → suggests log transformation applied") 
        print("- Stochastic_%D min=-0.067 → original data (no log)")
        print("- ADX range [1.77, 4.32] → suggests log transformation")
        print("- DI+ range [2.09, 64.09] → suggests log transformation")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
