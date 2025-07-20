#!/usr/bin/env python3
"""
Perfect Replication Verification Script
Compares feature-eng output with prediction_provider fe_replicator_feeder output
"""

import pandas as pd
import numpy as np
import os
import sys

def compare_datasets(ref_path, test_path, tolerance=1e-10):
    """Compare two CSV files with ultra-strict tolerance"""
    print(f"🔍 Loading reference: {ref_path}")
    if not os.path.exists(ref_path):
        print(f"❌ Reference file not found: {ref_path}")
        return False
        
    ref_df = pd.read_csv(ref_path)
    print(f"📊 Reference shape: {ref_df.shape}")
    print(f"📊 Reference columns: {list(ref_df.columns)}")
    
    print(f"🔍 Loading test: {test_path}")
    if not os.path.exists(test_path):
        print(f"❌ Test file not found: {test_path}")
        return False
        
    test_df = pd.read_csv(test_path)
    print(f"📊 Test shape: {test_df.shape}")
    print(f"📊 Test columns: {list(test_df.columns)}")
    
    # Check shapes and trim if needed
    if ref_df.shape[0] != test_df.shape[0]:
        print(f"📏 Different row counts: ref={ref_df.shape[0]}, test={test_df.shape[0]}")
        
        # Get common date range
        ref_start = pd.to_datetime(ref_df['DATE_TIME'].iloc[0])
        ref_end = pd.to_datetime(ref_df['DATE_TIME'].iloc[-1])
        
        test_start = pd.to_datetime(test_df['DATE_TIME'].iloc[0])
        test_end = pd.to_datetime(test_df['DATE_TIME'].iloc[-1])
        
        print(f"📅 Reference range: {ref_start} to {ref_end}")
        print(f"📅 Test range: {test_start} to {test_end}")
        
        # Find common range
        common_start = max(ref_start, test_start)
        common_end = min(ref_end, test_end)
        
        print(f"📅 Common range: {common_start} to {common_end}")
        
        # Trim both datasets to common range
        ref_mask = (pd.to_datetime(ref_df['DATE_TIME']) >= common_start) & (pd.to_datetime(ref_df['DATE_TIME']) <= common_end)
        test_mask = (pd.to_datetime(test_df['DATE_TIME']) >= common_start) & (pd.to_datetime(test_df['DATE_TIME']) <= common_end)
        
        ref_df = ref_df[ref_mask].reset_index(drop=True)
        test_df = test_df[test_mask].reset_index(drop=True)
        
        print(f"📊 After trimming - Reference: {ref_df.shape}, Test: {test_df.shape}")
        
    if ref_df.shape != test_df.shape:
        print(f"❌ SHAPE MISMATCH after trimming: {ref_df.shape} vs {test_df.shape}")
        return False
    
    # Check columns
    ref_cols = set(ref_df.columns)
    test_cols = set(test_df.columns)
    
    if ref_cols != test_cols:
        missing_in_test = ref_cols - test_cols
        extra_in_test = test_cols - ref_cols
        print(f"❌ COLUMN MISMATCH:")
        if missing_in_test:
            print(f"   Missing in test: {missing_in_test}")
        if extra_in_test:
            print(f"   Extra in test: {extra_in_test}")
        return False
    
    # Compare numeric columns with tolerance
    numeric_cols = ref_df.select_dtypes(include=[np.number]).columns
    print(f"🔢 Comparing {len(numeric_cols)} numeric columns...")
    
    perfect_match = True
    for col in numeric_cols:
        if col == 'DATE_TIME':  # Skip datetime if present
            continue
            
        ref_values = ref_df[col].values
        test_values = test_df[col].values
        
        # Handle NaN values
        ref_nan_mask = np.isnan(ref_values)
        test_nan_mask = np.isnan(test_values)
        
        if not np.array_equal(ref_nan_mask, test_nan_mask):
            print(f"❌ NaN MISMATCH in {col}")
            print(f"   Ref NaN count: {np.sum(ref_nan_mask)}")
            print(f"   Test NaN count: {np.sum(test_nan_mask)}")
            perfect_match = False
            continue
        
        # Compare non-NaN values
        valid_mask = ~ref_nan_mask
        if np.sum(valid_mask) == 0:
            continue  # All NaN, skip
            
        ref_valid = ref_values[valid_mask]
        test_valid = test_values[valid_mask]
        
        # Check if arrays are close within tolerance
        if not np.allclose(ref_valid, test_valid, atol=tolerance, rtol=tolerance):
            diff = np.abs(ref_valid - test_valid)
            max_diff = np.max(diff)
            max_diff_idx = np.argmax(diff)
            
            print(f"❌ MISMATCH in {col}:")
            print(f"   Max difference: {max_diff:.2e}")
            print(f"   At index {max_diff_idx}: ref={ref_valid[max_diff_idx]:.10f}, test={test_valid[max_diff_idx]:.10f}")
            print(f"   Sample diffs: {diff[:5]}")
            perfect_match = False
        else:
            print(f"✅ PERFECT MATCH: {col}")
    
    return perfect_match

def main():
    """Main comparison function"""
    # Paths
    fe_reference = "/home/harveybc/Documents/GitHub/feature-eng/perfect_reference_raw.csv"
    
    print("=" * 80)
    print("🎯 PERFECT REPLICATION VERIFICATION")
    print("=" * 80)
    
    # Load and process with fe_replicator_feeder
    print("📝 Running prediction_provider fe_replicator_feeder...")
    
    try:
        # Import the feeder plugin
        sys.path.append('/home/harveybc/Documents/GitHub/prediction_provider')
        from plugins_feeder.fe_replicator_feeder import FeReplicatorFeeder
        
        # Create feeder instance
        feeder = FeReplicatorFeeder()
        
        # Load FE configuration
        fe_config_path = "/home/harveybc/Documents/GitHub/feature-eng/fe_config.json"
        print(f"📝 Loading FE config from: {fe_config_path}")
        feeder.load_fe_config(fe_config_path)
        
        # Setup FE environment
        print("🔧 Setting up FE environment...")
        feeder.setup_feature_eng_environment()
        
        # Process the data
        print("🔄 Processing data with fe_replicator_feeder...")
        
        # Load input data
        input_csv = "/home/harveybc/Documents/GitHub/feature-eng/tests/data/eurusd_hour_2005_2020_ohlc.csv"
        input_data = pd.read_csv(input_csv)
        print(f"📊 Input data shape: {input_data.shape}")
        
        # Process with feeder
        df = feeder.process_data_with_fe_pipeline(input_data)
        
        # Save test output
        test_output = "/home/harveybc/Documents/GitHub/prediction_provider/fe_replication_test.csv"
        df.to_csv(test_output, index=False)
        print(f"💾 Saved test output: {test_output}")
        
        # Compare results
        print("\n" + "=" * 80)
        print("🔍 COMPARISON RESULTS")
        print("=" * 80)
        
        perfect = compare_datasets(fe_reference, test_output, tolerance=1e-10)
        
        print("\n" + "=" * 80)
        if perfect:
            print("🎉 PERFECT REPLICATION ACHIEVED! 🎉")
            print("✅ All features match exactly within 1e-10 tolerance")
        else:
            print("❌ REPLICATION FAILED")
            print("💡 Some features do not match within tolerance")
        print("=" * 80)
        
        return perfect
        
    except Exception as e:
        print(f"❌ ERROR during processing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
