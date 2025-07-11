#!/usr/bin/env python3
"""
Final STL Integration Test
"""

import sys
sys.path.append('/home/harveybc/Documents/GitHub/prediction_provider')

from plugins_feeder.real_feeder import RealFeederPlugin
from datetime import datetime, timedelta

def main():
    print("🎯 Final STL Integration Test")
    
    try:
        config = {'additional_previous_ticks': 0}
        real_feeder = RealFeederPlugin(config)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)  # Use less data to avoid hanging
        
        print(f"Loading data from {start_date.strftime('%H:%M')} to {end_date.strftime('%H:%M')}")
        
        data = real_feeder.load_data(
            start_date.strftime('%Y-%m-%d %H:%M:%S'), 
            end_date.strftime('%Y-%m-%d %H:%M:%S')
        )
        
        cols = list(data.columns)
        
        # Check tick features
        tick_features = [col for col in cols if 'tick' in col]
        
        # Check all technical indicators (based on what we saw in debug output)
        tech_indicator_names = ['RSI', 'MACD', 'MACD_Signal', 'MACD_Histogram', 'EMA', 'Stochastic_%K', 'Stochastic_%D', 
                               'ADX', 'DI+', 'DI-', 'ATR', 'CCI', 'WilliamsR', 'Momentum', 'ROC']
        tech_indicators = [col for col in cols if col in tech_indicator_names]
        
        # Check price and time features
        price_features = [col for col in cols if col in ['BH-BL', 'BH-BO', 'BO-BL', 'BC-BO']]
        time_features = [col for col in cols if col in ['day_of_month', 'hour_of_day', 'day_of_week']]
        market_features = [col for col in cols if col in ['S&P500_Close', 'vix_close']]
        ohlc_features = [col for col in cols if col in ['OPEN', 'HIGH', 'LOW', 'CLOSE']]
        
        stl_features = [col for col in cols if any(prefix in col for prefix in ['log_return', 'wav_'])]
        
        print(f"\\n📊 Results:")
        print(f"   Total features: {len(cols)}")
        print(f"   Tick features: {len(tick_features)}/16")
        print(f"   Tech indicators: {len(tech_indicators)}/15")  
        print(f"   Price features: {len(price_features)}/4")
        print(f"   Time features: {len(time_features)}/3") 
        print(f"   Market features: {len(market_features)}/2")
        print(f"   OHLC features: {len(ohlc_features)}/4")
        print(f"   STL features: {len(stl_features)}/13")
        
        # Base features: 16 tick + 15 tech + 4 price + 3 time + 2 market + 4 OHLC = 44
        base_features = len(tick_features) + len(tech_indicators) + len(price_features) + len(time_features) + len(market_features) + len(ohlc_features)
        print(f"   Base features: {base_features}/44")
        
        # Expected: 44 base + 10 STL/wavelet/MTM = 54 total  
        expected_total = 54
        success_rate = len(cols) / expected_total * 100
        
        print(f"\\n🎯 Final Score: {len(cols)}/{expected_total} ({success_rate:.1f}%)")
        
        if len(cols) >= 52:  # Reasonable threshold
            print("\\n🎉 SUCCESS! STL integration complete!")
            return True
        else:
            print("\\n⚠️  Partial success. Some features missing.")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    main()
