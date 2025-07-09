#!/usr/bin/env python3
"""
Data Normalizer Module

Handles all data normalization operations using min/max values
from training data to ensure consistency with the prediction model.
"""

import pandas as pd
import numpy as np
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class DataNormalizer:
    """
    Handles data normalization using pre-computed min/max values.
    Ensures consistency with training data normalization.
    """
    
    def __init__(self, normalization_file: str):
        """
        Initialize normalizer with min/max values from training.
        
        Args:
            normalization_file: Path to JSON file with min/max values
        """
        self.normalization_file = normalization_file
        self.min_max_values = self._load_normalization_values()
    
    def _load_normalization_values(self) -> Dict[str, Any]:
        """Load min/max values from the normalization file."""
        try:
            with open(self.normalization_file, 'r') as f:
                data = json.load(f)
            
            if 'min_max_values' in data:
                min_max_values = data['min_max_values']
                logger.info(f"Loaded normalization values for {len(min_max_values)} columns")
                return min_max_values
            else:
                logger.error("No 'min_max_values' key found in normalization file")
                return {}
                
        except Exception as e:
            logger.error(f"Error loading normalization values: {e}")
            return {}
    
    def normalize_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize data using the loaded min/max values.
        
        Args:
            data: Raw data to normalize
            
        Returns:
            Normalized data using (value - min) / (max - min) formula
        """
        try:
            normalized_data = data.copy()
            
            for column in data.columns:
                if column in self.min_max_values:
                    min_val = self.min_max_values[column]['min']
                    max_val = self.min_max_values[column]['max']
                    
                    # Apply normalization: (value - min) / (max - min)
                    if max_val != min_val:  # Avoid division by zero
                        normalized_data[column] = (data[column] - min_val) / (max_val - min_val)
                    else:
                        # If min == max, set to 0 (constant feature)
                        normalized_data[column] = 0
                        logger.warning(f"Column {column} has min == max, setting to 0")
                else:
                    logger.warning(f"No normalization values found for column: {column}")
                    # Keep original values if no normalization data available
            
            logger.info(f"Normalized data shape: {normalized_data.shape}")
            return normalized_data
            
        except Exception as e:
            logger.error(f"Error normalizing data: {e}")
            return data
    
    def denormalize_data(self, normalized_data: pd.DataFrame, columns: Optional[list] = None) -> pd.DataFrame:
        """
        Denormalize data back to original scale.
        
        Args:
            normalized_data: Normalized data to convert back
            columns: Specific columns to denormalize (all if None)
            
        Returns:
            Denormalized data
        """
        try:
            denormalized_data = normalized_data.copy()
            
            columns_to_process = columns if columns else normalized_data.columns
            
            for column in columns_to_process:
                if column in self.min_max_values:
                    min_val = self.min_max_values[column]['min']
                    max_val = self.min_max_values[column]['max']
                    
                    # Apply denormalization: value * (max - min) + min
                    denormalized_data[column] = normalized_data[column] * (max_val - min_val) + min_val
                else:
                    logger.warning(f"No normalization values found for column: {column}")
            
            logger.info(f"Denormalized data shape: {denormalized_data.shape}")
            return denormalized_data
            
        except Exception as e:
            logger.error(f"Error denormalizing data: {e}")
            return normalized_data
    
    def get_normalization_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the normalization values.
        
        Returns:
            Dictionary with normalization statistics
        """
        if not self.min_max_values:
            return {}
        
        stats = {
            'total_columns': len(self.min_max_values),
            'columns': list(self.min_max_values.keys()),
            'ranges': {}
        }
        
        for column, values in self.min_max_values.items():
            range_val = values['max'] - values['min']
            stats['ranges'][column] = {
                'min': values['min'],
                'max': values['max'],
                'range': range_val
            }
        
        return stats
    
    def validate_normalization(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Validate that normalized data is in expected range [0, 1].
        
        Args:
            data: Normalized data to validate
            
        Returns:
            Dictionary with validation results
        """
        validation_results = {
            'valid': True,
            'issues': [],
            'statistics': {}
        }
        
        try:
            for column in data.columns:
                col_min = data[column].min()
                col_max = data[column].max()
                
                validation_results['statistics'][column] = {
                    'min': col_min,
                    'max': col_max,
                    'mean': data[column].mean(),
                    'std': data[column].std()
                }
                
                # Check if values are outside [0, 1] range (with small tolerance)
                if col_min < -0.01 or col_max > 1.01:
                    validation_results['valid'] = False
                    validation_results['issues'].append(
                        f"Column {column} has values outside [0,1]: min={col_min:.4f}, max={col_max:.4f}"
                    )
            
            if validation_results['valid']:
                logger.info("Normalization validation passed")
            else:
                logger.warning(f"Normalization validation issues: {validation_results['issues']}")
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating normalization: {e}")
            validation_results['valid'] = False
            validation_results['issues'].append(f"Validation error: {e}")
            return validation_results
