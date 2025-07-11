#!/usr/bin/env python3
"""
Test specific technical indicators
"""

import sys
sys.path.append('/home/harveybc/Documents/GitHub/prediction_provider')

import pandas as pd
import numpy as np
import pandas_ta as ta
from plugins_feeder.real_feeder import RealFeederPlugin
from datetime import datetime, timedelta

def test_macd_stoch():
    print("🧪 Testing MACD and Stochastic specifically...")
    
    # Get some sample data
    config = {'additional_previous_ticks': 0}
    real_feeder = RealFeederPlugin(config)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1)
    
    hourly_data, data_15m, data_30m = real_feeder.data_fetcher.fetch_all_timeframes(start_date, end_date)
    feature_data = real_feeder.feature_generator.generate_all_features(hourly_data, data_15m, data_30m, 0)
    
    close_data = feature_data['CLOSE']
    high_data = feature_data['HIGH']
    low_data = feature_data['LOW']
    
    print(f"Close data shape: {close_data.shape}")
    print(f"Close data sample: {close_data.head()}")
    
    # Test MACD directly
    try:
        print("\\n📈 Testing MACD directly...")
        macd_result = ta.macd(close_data)
        print(f"MACD result type: {type(macd_result)}")
        if macd_result is not None:
            print(f"MACD columns: {list(macd_result.columns)}")
            print(f"MACD shape: {macd_result.shape}")
        else:
            print("MACD returned None")
    except Exception as e:
        print(f"MACD error: {e}")
    
    # Test Stochastic directly  
    try:
        print("\\n📊 Testing Stochastic directly...")
        stoch_result = ta.stoch(high_data, low_data, close_data)
        print(f"Stochastic result type: {type(stoch_result)}")
        if stoch_result is not None:
            print(f"Stochastic columns: {list(stoch_result.columns)}")
            print(f"Stochastic shape: {stoch_result.shape}")
        else:
            print("Stochastic returned None")
    except Exception as e:
        print(f"Stochastic error: {e}")

if __name__ == "__main__":
    test_macd_stoch()
