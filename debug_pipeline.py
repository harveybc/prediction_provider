#!/usr/bin/env python3
"""
Debug the data pipeline step by step
"""

import sys
sys.path.append('/home/harveybc/Documents/GitHub/prediction_provider')

from plugins_feeder.real_feeder import RealFeederPlugin
from datetime import datetime, timedelta

def main():
    print("🔧 Debug Pipeline Test")
    
    try:
        config = {'additional_previous_ticks': 0}
        real_feeder = RealFeederPlugin(config)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)
        
        print(f"Testing data pipeline from {start_date.strftime('%H:%M')} to {end_date.strftime('%H:%M')}")
        
        # Step 1: Test data fetcher
        print("\n📡 Step 1: Testing data fetcher...")
        hourly_data, data_15m, data_30m = real_feeder.data_fetcher.fetch_all_timeframes(start_date, end_date)
        
        print(f"Hourly data shape: {hourly_data.shape if not hourly_data.empty else 'Empty'}")
        print(f"15m data shape: {data_15m.shape if not data_15m.empty else 'Empty'}")
        print(f"30m data shape: {data_30m.shape if not data_30m.empty else 'Empty'}")
        
        if hourly_data.empty:
            print("❌ No hourly data - stopping test")
            return
        
        # Step 2: Test feature generator
        print("\n🔧 Step 2: Testing feature generator...")
        feature_data = real_feeder.feature_generator.generate_all_features(
            hourly_data, data_15m, data_30m, 0
        )
        
        print(f"Feature data type: {type(feature_data)}")
        print(f"Feature data shape: {feature_data.shape if feature_data is not None else 'None'}")
        print(f"Feature data columns: {list(feature_data.columns) if feature_data is not None else 'None'}")
        
        if feature_data is None or feature_data.empty:
            print("❌ Feature generation failed - stopping test")
            return
        
        # Check for OHLC columns
        ohlc_cols = ['OPEN', 'HIGH', 'LOW', 'CLOSE']
        missing_ohlc = [col for col in ohlc_cols if col not in feature_data.columns]
        print(f"OHLC columns present: {[col for col in ohlc_cols if col in feature_data.columns]}")
        print(f"Missing OHLC columns: {missing_ohlc}")
        
        # Step 3: Test technical indicators
        print("\n📈 Step 3: Testing technical indicators...")
        if missing_ohlc:
            print(f"❌ Missing OHLC columns, cannot test technical indicators: {missing_ohlc}")
            return
        
        tech_data = real_feeder.tech_calculator.calculate_all_indicators(feature_data)
        
        print(f"Tech data shape: {tech_data.shape if tech_data is not None else 'None'}")
        print(f"Tech data columns: {list(tech_data.columns) if tech_data is not None else 'None'}")
        
        print("\n✅ Pipeline debug complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
