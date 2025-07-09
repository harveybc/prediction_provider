#!/usr/bin/env python3
"""
Data Validator Module

Handles all data validation operations including comparison with historical data
and validation of data quality and consistency.
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class DataValidator:
    """
    Handles data validation operations.
    Validates data quality, consistency, and comparison with historical data.
    """
    
    def __init__(self, reference_data_file: Optional[str] = None):
        """
        Initialize validator with optional reference data.
        
        Args:
            reference_data_file: Path to historical reference data CSV
        """
        self.reference_data_file = reference_data_file
        self.reference_data = self._load_reference_data() if reference_data_file else None
    
    def _load_reference_data(self) -> Optional[pd.DataFrame]:
        """Load reference data for validation."""
        try:
            reference_data = pd.read_csv(self.reference_data_file)
            
            # Convert DATE_TIME to datetime if it exists
            if 'DATE_TIME' in reference_data.columns:
                reference_data['DATE_TIME'] = pd.to_datetime(reference_data['DATE_TIME'])
                reference_data = reference_data.set_index('DATE_TIME')
            
            logger.info(f"Loaded reference data shape: {reference_data.shape}")
            return reference_data
            
        except Exception as e:
            logger.error(f"Error loading reference data: {e}")
            return None
    
    def validate_data_quality(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Validate general data quality.
        
        Args:
            data: Data to validate
            
        Returns:
            Dictionary with validation results
        """
        validation_results = {
            'valid': True,
            'issues': [],
            'statistics': {}
        }
        
        try:
            # Check for empty data
            if data.empty:
                validation_results['valid'] = False
                validation_results['issues'].append("Data is empty")
                return validation_results
            
            # Check for NaN values
            nan_counts = data.isnull().sum()
            if nan_counts.any():
                validation_results['issues'].append(f"NaN values found: {nan_counts[nan_counts > 0].to_dict()}")
                
            # Check for infinite values
            inf_counts = np.isinf(data.select_dtypes(include=[np.number])).sum()
            if inf_counts.any():
                validation_results['valid'] = False
                validation_results['issues'].append(f"Infinite values found: {inf_counts[inf_counts > 0].to_dict()}")
            
            # Basic statistics
            validation_results['statistics'] = {
                'shape': data.shape,
                'columns': list(data.columns),
                'dtypes': data.dtypes.to_dict(),
                'memory_usage': data.memory_usage(deep=True).sum(),
                'nan_counts': nan_counts.to_dict()
            }
            
            logger.info(f"Data quality validation completed. Valid: {validation_results['valid']}")
            return validation_results
            
        except Exception as e:
            logger.error(f"Error in data quality validation: {e}")
            validation_results['valid'] = False
            validation_results['issues'].append(f"Validation error: {e}")
            return validation_results
    
    def validate_against_reference(self, data: pd.DataFrame, tolerance: float = 0.01) -> Dict[str, Any]:
        """
        Validate data against reference/historical data.
        
        Args:
            data: Data to validate
            tolerance: Tolerance for numerical comparisons
            
        Returns:
            Dictionary with validation results
        """
        validation_results = {
            'valid': True,
            'issues': [],
            'comparisons': {}
        }
        
        if self.reference_data is None:
            validation_results['issues'].append("No reference data available for comparison")
            return validation_results
        
        try:
            # Find overlapping timestamps
            if hasattr(data.index, 'intersection'):
                common_timestamps = data.index.intersection(self.reference_data.index)
            else:
                common_timestamps = []
            
            if len(common_timestamps) == 0:
                validation_results['issues'].append("No overlapping timestamps with reference data")
                return validation_results
            
            logger.info(f"Comparing {len(common_timestamps)} overlapping timestamps")
            
            # Compare common columns
            common_columns = set(data.columns).intersection(set(self.reference_data.columns))
            
            for column in common_columns:
                try:
                    # Get data for comparison
                    test_values = data.loc[common_timestamps, column]
                    ref_values = self.reference_data.loc[common_timestamps, column]
                    
                    # Calculate differences
                    differences = np.abs(test_values - ref_values)
                    max_diff = differences.max()
                    mean_diff = differences.mean()
                    
                    validation_results['comparisons'][column] = {
                        'max_difference': max_diff,
                        'mean_difference': mean_diff,
                        'samples_compared': len(common_timestamps),
                        'within_tolerance': max_diff <= tolerance
                    }
                    
                    if max_diff > tolerance:
                        validation_results['valid'] = False
                        validation_results['issues'].append(
                            f"Column {column}: max difference {max_diff:.6f} > tolerance {tolerance}"
                        )
                    
                except Exception as e:
                    validation_results['issues'].append(f"Error comparing column {column}: {e}")
            
            logger.info(f"Reference validation completed. Valid: {validation_results['valid']}")
            return validation_results
            
        except Exception as e:
            logger.error(f"Error in reference validation: {e}")
            validation_results['valid'] = False
            validation_results['issues'].append(f"Reference validation error: {e}")
            return validation_results
    
    def validate_column_structure(self, data: pd.DataFrame, expected_columns: list) -> Dict[str, Any]:
        """
        Validate that data has expected column structure.
        
        Args:
            data: Data to validate
            expected_columns: List of expected column names
            
        Returns:
            Dictionary with validation results
        """
        validation_results = {
            'valid': True,
            'issues': [],
            'column_analysis': {}
        }
        
        try:
            data_columns = set(data.columns)
            expected_columns_set = set(expected_columns)
            
            # Missing columns
            missing_columns = expected_columns_set - data_columns
            if missing_columns:
                validation_results['valid'] = False
                validation_results['issues'].append(f"Missing columns: {list(missing_columns)}")
            
            # Extra columns
            extra_columns = data_columns - expected_columns_set
            if extra_columns:
                validation_results['issues'].append(f"Extra columns: {list(extra_columns)}")
            
            validation_results['column_analysis'] = {
                'expected_count': len(expected_columns),
                'actual_count': len(data.columns),
                'missing_columns': list(missing_columns),
                'extra_columns': list(extra_columns),
                'common_columns': list(data_columns.intersection(expected_columns_set))
            }
            
            logger.info(f"Column structure validation completed. Valid: {validation_results['valid']}")
            return validation_results
            
        except Exception as e:
            logger.error(f"Error in column structure validation: {e}")
            validation_results['valid'] = False
            validation_results['issues'].append(f"Column validation error: {e}")
            return validation_results
    
    def validate_timestamp_range(self, data: pd.DataFrame, 
                                expected_start: datetime, expected_end: datetime) -> Dict[str, Any]:
        """
        Validate that data covers expected timestamp range.
        
        Args:
            data: Data to validate
            expected_start: Expected start timestamp
            expected_end: Expected end timestamp
            
        Returns:
            Dictionary with validation results
        """
        validation_results = {
            'valid': True,
            'issues': [],
            'timestamp_analysis': {}
        }
        
        try:
            if data.empty:
                validation_results['valid'] = False
                validation_results['issues'].append("Data is empty")
                return validation_results
            
            actual_start = data.index.min()
            actual_end = data.index.max()
            
            validation_results['timestamp_analysis'] = {
                'expected_start': expected_start,
                'expected_end': expected_end,
                'actual_start': actual_start,
                'actual_end': actual_end,
                'expected_count': len(pd.date_range(expected_start, expected_end, freq='H')),
                'actual_count': len(data)
            }
            
            # Check if actual range covers expected range
            if actual_start > expected_start:
                validation_results['issues'].append(
                    f"Data starts later than expected: {actual_start} > {expected_start}"
                )
            
            if actual_end < expected_end:
                validation_results['issues'].append(
                    f"Data ends earlier than expected: {actual_end} < {expected_end}"
                )
            
            logger.info(f"Timestamp range validation completed. Valid: {validation_results['valid']}")
            return validation_results
            
        except Exception as e:
            logger.error(f"Error in timestamp range validation: {e}")
            validation_results['valid'] = False
            validation_results['issues'].append(f"Timestamp validation error: {e}")
            return validation_results
