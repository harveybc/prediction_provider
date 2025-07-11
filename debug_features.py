#!/usr/bin/env python3
"""
Quick debug test for feature preservation
"""

import sys
sys.path.append('/home/harveybc/Documents/GitHub/prediction_provider')

import pandas as pd
from plugins_feeder.technical_indicators import TechnicalIndicatorCalculator

def test_tech_indicators():
    # Test data with S&P500 and VIX
    data = pd.DataFrame({
        'OPEN': [1.17, 1.18, 1.19],
        'HIGH': [1.18, 1.19, 1.20], 
        'LOW': [1.16, 1.17, 1.18],
        'CLOSE': [1.17, 1.18, 1.19],
        'S&P500_Close': [4500, 4510, 4520],
        'vix_close': [20, 21, 22]
    })

    calc = TechnicalIndicatorCalculator()
    result = calc.calculate_all_indicators(data)

    print('Input columns:', list(data.columns))
    print('Output columns:', list(result.columns))
    print('S&P500 preserved:', 'S&P500_Close' in result.columns)
    print('VIX preserved:', 'vix_close' in result.columns)

if __name__ == "__main__":
    test_tech_indicators()
