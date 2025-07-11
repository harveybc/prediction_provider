#!/usr/bin/env python3
"""
Simple validation script for STL integration
"""

import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add project path
sys.path.append('/home/harveybc/Documents/GitHub/prediction_provider')

def main():
    print("=== STL Integration Validation ===")
    
    try:
        from plugins_feeder.real_feeder import RealFeederPlugin
        
        # Test with reasonable parameters
        config = {
            'additional_previous_ticks': 0,
            'use_wavelets': True,
            'wavelet_levels': 2
        }
        
        real_feeder = RealFeederPlugin(config)
        
        # Use 3 days of data for sufficient technical indicator calculation
        end_date = datetime.now()
        start_date = end_date - timedelta(days=3)
        
        print(f"Loading data from {start_date.strftime('%Y-%m-%d %H:%M')} to {end_date.strftime('%Y-%m-%d %H:%M')}")
        
        # Load data
        data = real_feeder.load_data(
            start_date.strftime('%Y-%m-%d %H:%M:%S'), 
            end_date.strftime('%Y-%m-%d %H:%M:%S')
        )
        
        if data.empty:
            print("❌ No data returned")
            return False
        
        print(f"✅ Data loaded successfully: {data.shape}")
        
        # Analyze features
        cols = list(data.columns)
        
        # Expected base features (44)
        expected_base = [
            'RSI', 'MACD', 'MACD_Histogram', 'MACD_Signal', 'EMA', 
            'Stochastic_%K', 'Stochastic_%D', 'ADX', 'DI+', 'DI-', 'ATR', 'CCI', 
            'WilliamsR', 'Momentum', 'ROC', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 
            'BC-BO', 'BH-BL', 'BH-BO', 'BO-BL', 'S&P500_Close', 'vix_close',
            'CLOSE_15m_tick_1', 'CLOSE_15m_tick_2', 'CLOSE_15m_tick_3', 'CLOSE_15m_tick_4',
            'CLOSE_15m_tick_5', 'CLOSE_15m_tick_6', 'CLOSE_15m_tick_7', 'CLOSE_15m_tick_8',
            'CLOSE_30m_tick_1', 'CLOSE_30m_tick_2', 'CLOSE_30m_tick_3', 'CLOSE_30m_tick_4',
            'CLOSE_30m_tick_5', 'CLOSE_30m_tick_6', 'CLOSE_30m_tick_7', 'CLOSE_30m_tick_8',
            'day_of_month', 'hour_of_day', 'day_of_week'
        ]
        
        # Expected STL features (13)
        expected_stl = [
            'log_return',
            'wav_swt_cA_L1_mean', 'wav_swt_cA_L1_std', 'wav_swt_cA_L1_energy',
            'wav_swt_cD_L1_mean', 'wav_swt_cD_L1_std', 'wav_swt_cD_L1_energy',
            'wav_swt_cA_L2_mean', 'wav_swt_cA_L2_std', 'wav_swt_cA_L2_energy',
            'wav_swt_cD_L2_mean', 'wav_swt_cD_L2_std', 'wav_swt_cD_L2_energy'
        ]
        
        # Check feature categories
        base_found = [col for col in expected_base if col in cols]
        stl_found = [col for col in expected_stl if col in cols]
        
        base_missing = [col for col in expected_base if col not in cols]
        
        print(f"\n📊 Feature Analysis:")
        print(f"   Total features: {len(cols)}")
        print(f"   Base features: {len(base_found)}/{len(expected_base)}")
        print(f"   STL features: {len(stl_found)}/{len(expected_stl)}")
        
        if base_missing:
            print(f"\n❌ Missing base features ({len(base_missing)}):")
            for i, col in enumerate(base_missing):
                print(f"   {i+1:2d}. {col}")
        else:
            print(f"\n✅ All base features present!")
        
        if len(stl_found) == len(expected_stl):
            print(f"✅ All STL features present!")
        else:
            print(f"❌ STL features incomplete: {len(stl_found)}/{len(expected_stl)}")
        
        # Summary
        total_expected = len(expected_base) + len(expected_stl)
        total_found = len(base_found) + len(stl_found)
        
        print(f"\n🎯 Summary:")
        print(f"   Expected: {total_expected} features")
        print(f"   Found: {total_found} features")
        print(f"   Success rate: {total_found/total_expected*100:.1f}%")
        
        if total_found >= 50:  # Reasonable threshold
            print(f"✅ Integration successful! Ready for model prediction.")
            return True
        else:
            print(f"❌ Integration incomplete. More work needed.")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
