#!/usr/bin/env python3
"""
Test script to validate that the RealFeederPlugin's technical indicators 
match those in the normalized training data (d4 dataset).

This test:
1. Loads normalized_d4.csv and phase_3_debug_out.json
2. Denormalizes HLOC columns using min/max from the debug file
3. Recalculates technical indicators using the same logic as feature-eng
4. Normalizes the recalculated indicators using the same min/max
5. Compares the normalized values to those in normalized_d4.csv
"""

import pandas as pd
import numpy as np
import json
import pandas_ta as ta
import sys
import os

# Add the plugins_feeder directory to the Python path
sys.path.append('/home/harveybc/Documents/GitHub/prediction_provider/plugins_feeder')

from technical_indicators import TechnicalIndicatorCalculator

def load_test_data():
    """Load the normalized training data and normalization parameters."""
    print("Loading test data...")
    
    # Load normalized training data
    d4_path = '/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/normalized_d4.csv'
    normalized_d4 = pd.read_csv(d4_path)
    print(f"Loaded normalized_d4.csv with shape: {normalized_d4.shape}")
    
    # Load normalization parameters
    debug_path = '/home/harveybc/Documents/GitHub/prediction_provider/examples/data/phase_3/phase_3_debug_out.json'
    with open(debug_path, 'r') as f:
        debug_data = json.load(f)
    
    # Extract min and max values from the debug data format
    min_vals = {}
    max_vals = {}
    for feature, values in debug_data.items():
        min_vals[feature] = values['min']
        max_vals[feature] = values['max']
    
    print(f"Loaded normalization parameters for {len(min_vals)} columns")
    
    return normalized_d4, min_vals, max_vals

def denormalize_data(normalized_data, min_vals, max_vals, columns):
    """Denormalize specified columns using min/max values."""
    denormalized = normalized_data.copy()
    
    for col in columns:
        if col in min_vals and col in max_vals:
            min_val = min_vals[col]
            max_val = max_vals[col]
            
            # Denormalize: original = normalized * (max - min) + min
            denormalized[col] = normalized_data[col] * (max_val - min_val) + min_val
            print(f"Denormalized {col}: range [{min_val:.6f}, {max_val:.6f}]")
        else:
            print(f"Warning: No normalization parameters found for {col}")
    
    return denormalized

def normalize_data(data, min_vals, max_vals, columns):
    """Normalize specified columns using min/max values."""
    normalized = data.copy()
    
    for col in columns:
        if col in min_vals and col in max_vals:
            min_val = min_vals[col]
            max_val = max_vals[col]
            
            # Normalize: normalized = (original - min) / (max - min)
            if max_val != min_val:
                normalized[col] = (data[col] - min_val) / (max_val - min_val)
            else:
                normalized[col] = 0.0  # Handle case where min == max
        else:
            print(f"Warning: No normalization parameters found for {col}")
    
    return normalized

def recalculate_technical_indicators(hloc_data):
    """Recalculate technical indicators using the same logic as feature-eng."""
    print("Recalculating technical indicators...")
    
    # Initialize the technical indicator calculator
    calculator = TechnicalIndicatorCalculator()
    
    # Prepare data in the expected format (with proper column names)
    data = pd.DataFrame({
        'Open': hloc_data['OPEN'],
        'High': hloc_data['HIGH'], 
        'Low': hloc_data['LOW'],
        'Close': hloc_data['CLOSE']
    })
    
    # Calculate technical indicators
    indicators = calculator.calculate_all_indicators(data)
    
    print(f"Calculated {len(indicators.columns)} technical indicators")
    print(f"Indicator columns: {list(indicators.columns)}")
    
    return indicators

def align_data_for_comparison(original_data, recalculated_data, window_offset=200):
    """
    Align data for comparison, accounting for indicator calculation windows.
    
    Args:
        original_data: Original normalized data from d4
        recalculated_data: Recalculated and renormalized indicators
        window_offset: Number of initial rows to skip due to indicator windows
    
    Returns:
        Tuple of aligned dataframes for comparison
    """
    print(f"Aligning data with window offset: {window_offset}")
    
    # Skip the first window_offset rows to account for indicator calculation windows
    original_aligned = original_data.iloc[window_offset:].copy()
    recalculated_aligned = recalculated_data.iloc[window_offset:].copy()
    
    # Take only the first 1000 rows for comparison as planned
    max_rows = min(1000, len(original_aligned), len(recalculated_aligned))
    original_aligned = original_aligned.iloc[:max_rows]
    recalculated_aligned = recalculated_aligned.iloc[:max_rows]
    
    print(f"Aligned data shapes - Original: {original_aligned.shape}, Recalculated: {recalculated_aligned.shape}")
    
    return original_aligned, recalculated_aligned

def compare_indicators(original_data, recalculated_data, min_vals, max_vals, tolerance=1e-4):
    """Compare technical indicators between original and recalculated data."""
    print(f"Comparing indicators with tolerance: {tolerance}")
    
    # Get the technical indicator columns (excluding HLOC and other features)
    indicator_columns = []
    
    # Based on the feature-eng tech_indicator.py, these are the expected indicator columns
    expected_indicators = [
        'RSI', 'MACD', 'MACD_Histogram', 'MACD_Signal', 'EMA',
        'Stochastic_%K', 'Stochastic_%D', 'ADX', 'DI+', 'DI-', 'ATR',
        'CCI', 'BB_Upper', 'BB_Middle', 'BB_Lower', 'WilliamsR',
        'Momentum', 'ROC'
    ]
    
    # Find which indicators are present in both datasets
    for indicator in expected_indicators:
        if indicator in original_data.columns and indicator in recalculated_data.columns:
            indicator_columns.append(indicator)
    
    print(f"Found {len(indicator_columns)} matching indicator columns for comparison")
    print(f"Indicator columns: {indicator_columns}")
    
    comparison_results = {}
    
    for col in indicator_columns:
        original_values = original_data[col].values
        recalculated_values = recalculated_data[col].values
        
        # Calculate differences
        diff = np.abs(original_values - recalculated_values)
        max_diff = np.max(diff)
        mean_diff = np.mean(diff)
        
        # Check if values are within tolerance
        within_tolerance = np.all(diff <= tolerance)
        
        comparison_results[col] = {
            'max_diff': max_diff,
            'mean_diff': mean_diff,
            'within_tolerance': within_tolerance,
            'original_range': f"[{np.min(original_values):.6f}, {np.max(original_values):.6f}]",
            'recalculated_range': f"[{np.min(recalculated_values):.6f}, {np.max(recalculated_values):.6f}]"
        }
        
        print(f"{col}:")
        print(f"  Max diff: {max_diff:.8f}")
        print(f"  Mean diff: {mean_diff:.8f}")
        print(f"  Within tolerance: {within_tolerance}")
        print(f"  Original range: {comparison_results[col]['original_range']}")
        print(f"  Recalculated range: {comparison_results[col]['recalculated_range']}")
        print()
    
    return comparison_results

def main():
    """Main test function."""
    print("=== Technical Indicator Validation Test ===")
    print()
    
    try:
        # 1. Load test data
        normalized_d4, min_vals, max_vals = load_test_data()
        print()
        
        # 2. Denormalize HLOC columns
        hloc_columns = ['OPEN', 'HIGH', 'LOW', 'CLOSE']
        denormalized_data = denormalize_data(normalized_d4, min_vals, max_vals, hloc_columns)
        print()
        
        # 3. Recalculate technical indicators
        recalculated_indicators = recalculate_technical_indicators(denormalized_data)
        print()
        
        # 4. Normalize the recalculated indicators
        indicator_columns = list(recalculated_indicators.columns)
        normalized_recalculated = normalize_data(recalculated_indicators, min_vals, max_vals, indicator_columns)
        print()
        
        # 5. Align data for comparison (skip initial rows due to indicator windows)
        original_aligned, recalculated_aligned = align_data_for_comparison(
            normalized_d4, normalized_recalculated, window_offset=200
        )
        print()
        
        # 6. Compare the indicators
        results = compare_indicators(original_aligned, recalculated_aligned, min_vals, max_vals)
        print()
        
        # 7. Summary
        print("=== SUMMARY ===")
        total_indicators = len(results)
        passed_indicators = sum(1 for r in results.values() if r['within_tolerance'])
        
        print(f"Total indicators compared: {total_indicators}")
        print(f"Indicators within tolerance: {passed_indicators}")
        print(f"Success rate: {passed_indicators/total_indicators*100:.1f}%" if total_indicators > 0 else "No indicators compared")
        
        if passed_indicators == total_indicators:
            print("✅ All technical indicators match the training data!")
        else:
            print("❌ Some indicators do not match - check the calculation logic")
            
            # Show which indicators failed
            failed = [col for col, result in results.items() if not result['within_tolerance']]
            print(f"Failed indicators: {failed}")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return passed_indicators == total_indicators

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
