#!/usr/bin/env python3
"""
Test script for RealFeederPlugin

This script tests the real feeder plugin functionality, including:
- Data fetching with start/end dates
- Multi-timeframe data integration
- Normalization and validation against historical data
"""

import sys
import os
import pandas as pd
from datetime import datetime, timedelta
import logging

# Add the plugins directory to the Python path
sys.path.append('/home/harveybc/Documents/GitHub/prediction_provider')

# Import the real feeder plugin
from plugins_feeder.real_feeder import RealFeederPlugin

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_real_feeder():
    """Test the real feeder plugin functionality."""
    
    print("="*60)
    print("TESTING REAL FEEDER PLUGIN")
    print("="*60)
    
    # Initialize the feeder plugin
    logger.info("Initializing RealFeederPlugin...")
    feeder = RealFeederPlugin()
    
    # Test 1: Basic functionality - fetch recent data
    print("\n" + "-"*40)
    print("TEST 1: Fetch recent data (default)")
    print("-"*40)
    
    try:
        # This uses the default fetch method
        recent_data = feeder.fetch()
        print(f"✓ Successfully fetched recent data: {recent_data.shape}")
        print(f"  Columns: {list(recent_data.columns)}")
        print(f"  Date range: {recent_data['DATE_TIME'].min()} to {recent_data['DATE_TIME'].max()}")
        
        # Display first few rows
        print("\nFirst 3 rows:")
        print(recent_data.head(3).to_string())
        
    except Exception as e:
        print(f"✗ Error in recent data fetch: {e}")
        return False
    
    # Test 2: Fetch data for a specific period
    print("\n" + "-"*40)
    print("TEST 2: Fetch data for specific period")
    print("-"*40)
    
    try:
        # Test with a specific date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)  # Last week
        
        period_data = feeder.fetch_data_for_period(
            start_date=start_date.strftime('%Y-%m-%d %H:%M:%S'),
            end_date=end_date.strftime('%Y-%m-%d %H:%M:%S'),
            additional_previous_ticks=24  # 24 hours buffer for indicators
        )
        
        print(f"✓ Successfully fetched period data: {period_data.shape}")
        print(f"  Requested: {start_date} to {end_date}")
        print(f"  Date range: {period_data['DATE_TIME'].min()} to {period_data['DATE_TIME'].max()}")
        
        # Check for all required columns
        required_columns = [
            'DATE_TIME', 'OPEN', 'HIGH', 'LOW', 'CLOSE',
            'BC-BO', 'BH-BL', 'BH-BO', 'BO-BL', 'S&P500_Close', 'vix_close',
            'CLOSE_15m_tick_1', 'CLOSE_15m_tick_2', 'CLOSE_15m_tick_3', 'CLOSE_15m_tick_4',
            'CLOSE_15m_tick_5', 'CLOSE_15m_tick_6', 'CLOSE_15m_tick_7', 'CLOSE_15m_tick_8',
            'CLOSE_30m_tick_1', 'CLOSE_30m_tick_2', 'CLOSE_30m_tick_3', 'CLOSE_30m_tick_4',
            'CLOSE_30m_tick_5', 'CLOSE_30m_tick_6', 'CLOSE_30m_tick_7', 'CLOSE_30m_tick_8',
            'day_of_month', 'hour_of_day', 'day_of_week'
        ]
        
        missing_columns = [col for col in required_columns if col not in period_data.columns]
        if missing_columns:
            print(f"✗ Missing required columns: {missing_columns}")
        else:
            print("✓ All required columns present")
            
        # Display sample of multi-timeframe data
        print("\nSample multi-timeframe tick data:")
        tick_columns = [col for col in period_data.columns if 'tick_' in col]
        if tick_columns:
            print(period_data[['DATE_TIME'] + tick_columns[:4]].head(2).to_string())
        
    except Exception as e:
        print(f"✗ Error in period data fetch: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 3: Validation against historical data (if available)
    print("\n" + "-"*40)
    print("TEST 3: Validate against historical data")
    print("-"*40)
    
    try:
        historical_csv = "/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv"
        
        # Check if historical data exists
        if os.path.exists(historical_csv):
            validation_results = feeder.validate_against_historical(period_data, historical_csv)
            
            print(f"✓ Validation completed")
            print(f"  Validation passed: {validation_results['validation_passed']}")
            print(f"  Common dates: {validation_results.get('total_common_dates', 0)}")
            print(f"  Error tolerance: {validation_results.get('tolerance', 'N/A')}")
            
            if 'column_comparisons' in validation_results:
                print("\nColumn comparison results:")
                for col, results in validation_results['column_comparisons'].items():
                    status = "✓" if results['within_tolerance'] else "✗"
                    print(f"  {status} {col}: max_diff={results['max_difference']:.6f}, mean_diff={results['mean_difference']:.6f}")
            
            if 'error' in validation_results:
                print(f"  Note: {validation_results['error']}")
                
        else:
            print(f"⚠ Historical data not found at {historical_csv}")
            print("  Skipping validation test")
            
    except Exception as e:
        print(f"✗ Error in validation: {e}")
        
    # Test 4: Check normalization 
    print("\n" + "-"*40)
    print("TEST 4: Check normalization")
    print("-"*40)
    
    try:
        # Check if normalization is being applied
        sample_cols = ['OPEN', 'HIGH', 'LOW', 'CLOSE', 'S&P500_Close', 'vix_close']
        available_cols = [col for col in sample_cols if col in period_data.columns]
        
        if available_cols:
            print("Normalization check (sample values):")
            for col in available_cols[:3]:  # Show first 3 columns
                values = period_data[col].dropna()
                if len(values) > 0:
                    print(f"  {col}: min={values.min():.6f}, max={values.max():.6f}, mean={values.mean():.6f}")
                    # Check if values look normalized (between 0 and 1, roughly)
                    if values.min() >= -0.1 and values.max() <= 1.1:
                        print(f"    ✓ Values appear normalized")
                    else:
                        print(f"    ⚠ Values may not be normalized")
        else:
            print("⚠ No sample columns available for normalization check")
            
    except Exception as e:
        print(f"✗ Error in normalization check: {e}")
    
    print("\n" + "="*60)
    print("TESTING COMPLETED")
    print("="*60)
    
    return True

def test_historical_data_compatibility():
    """Test compatibility with historical data structure."""
    
    print("\n" + "="*60)
    print("TESTING HISTORICAL DATA COMPATIBILITY")
    print("="*60)
    
    try:
        historical_csv = "/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv"
        
        if os.path.exists(historical_csv):
            # Load and analyze historical data
            hist_data = pd.read_csv(historical_csv)
            print(f"✓ Loaded historical data: {hist_data.shape}")
            print(f"  Columns: {len(hist_data.columns)}")
            print(f"  Date range: {hist_data['DATE_TIME'].min()} to {hist_data['DATE_TIME'].max()}")
            
            # Show column structure
            print(f"\nHistorical data columns:")
            for i, col in enumerate(hist_data.columns):
                print(f"  {i+1:2d}. {col}")
                
            # Show sample data
            print(f"\nSample historical data (first 2 rows):")
            print(hist_data.head(2).to_string())
            
        else:
            print(f"⚠ Historical data not found at {historical_csv}")
            
    except Exception as e:
        print(f"✗ Error loading historical data: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Starting Real Feeder Plugin Tests...")
    
    # Test historical data compatibility first
    test_historical_data_compatibility()
    
    # Test the real feeder plugin
    success = test_real_feeder()
    
    if success:
        print("\n🎉 All tests completed successfully!")
    else:
        print("\n❌ Some tests failed. Check the output above for details.")
        sys.exit(1)
