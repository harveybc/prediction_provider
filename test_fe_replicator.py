#!/usr/bin/env python3
"""
Test script for FE Replicator Feeder Plugin.
"""

import sys
import os

# Add prediction_provider to path
sys.path.insert(0, '/home/harveybc/Documents/GitHub/prediction_provider')

from plugins_feeder.fe_replicator_feeder import FeReplicatorFeeder

def test_fe_replicator():
    """Test the FE replicator feeder plugin."""
    print("=" * 60)
    print("TESTING FE REPLICATOR FEEDER PLUGIN")
    print("=" * 60)
    
    # Initialize the plugin
    feeder = FeReplicatorFeeder()
    
    # Set parameters
    feeder.set_params(
        fe_config_path='fe_config_test.json',  # Use the config we just generated
        input_csv_path='tests/data/eurusd_hour_2005_2020_ohlc.csv',
        output_csv_path='fe_replicated_output.csv',
        comparison_csv_path='perfect_reference.csv',  # Use the PERFECT reference for exact matching
        num_rows_to_process=1000,
        num_rows_to_compare=1000
    )
    
    # Process request
    request_data = {
        'symbol': 'EUR_USD',
        'test_replication': True
    }
    
    result = feeder.process_request(request_data)
    
    print("\n" + "=" * 60)
    print("RESULTS:")
    print("=" * 60)
    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}")
    
    if result['status'] == 'success':
        print(f"Processed rows: {result['processed_rows']}")
        print(f"Output path: {result['output_path']}")
        print(f"Exact match: {result['exact_match']}")
        
        comparison = result['comparison_result']
        print(f"Shape match: {comparison['shape_match']}")
        print(f"Columns match: {comparison['columns_match']}")
        
        if not result['exact_match']:
            print(f"Mismatched columns: {comparison['mismatched_columns']}")
            print(f"Feature-eng shape: {comparison['fe_shape']}")
            print(f"Replicated shape: {comparison['replicated_shape']}")
    
    return result

if __name__ == "__main__":
    result = test_fe_replicator()
    
    if result['exact_match']:
        print("\n🎉 SUCCESS: Perfect replicability achieved!")
        sys.exit(0)
    else:
        print("\n❌ FAILURE: Replicability test failed!")
        sys.exit(1)
