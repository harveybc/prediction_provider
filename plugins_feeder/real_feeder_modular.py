#!/usr/bin/env python3
"""
Real Feeder Plugin

This plugin fetches real market data from external APIs (Yahoo Finance)
and generates the required features for the prediction provider.

Features:
- Fetches EURUSD hourly HLOC data
- Fetches S&P500 and VIX hourly close data  
- Generates multi-timeframe tick features (15m, 30m)
- Calculates technical indicators matching feature-eng repo
- Normalizes data using training data min/max values
- Validates against historical data

The plugin efficiently fetches all required timeframes in minimal API calls
and generates features that exactly match the training data structure.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from .technical_indicators import TechnicalIndicatorCalculator
from .data_fetcher import DataFetcher
from .feature_generator import FeatureGenerator
from .data_normalizer import DataNormalizer
from .data_validator import DataValidator

logger = logging.getLogger(__name__)

class RealFeederPlugin:
    """
    Real market data feeder plugin.
    
    Fetches live market data and generates features matching the training data structure.
    Uses modular components for data fetching, feature generation, normalization, and validation.
    """
    
    # Plugin parameters with default values
    plugin_params = {
        "instrument": "EURUSD=X",
        "correlated_instruments": ["^GSPC", "^VIX"],
        "n_batches": 1,
        "batch_size": 256,
        "window_size": 256,
        "use_normalization_json": "examples/data/phase_3/phase_3_debug_out.json",
        "target_column": "CLOSE",
        "additional_previous_ticks": 50,  # Extra ticks for technical indicators
        "error_tolerance": 0.001  # Tolerance for validation against historical data
    }
    
    def __init__(self, config=None):
        """Initialize the real feeder plugin."""
        self.params = self.plugin_params.copy()
        
        if config:
            self.set_params(**config)
        
        # Initialize core components
        self.data_fetcher = DataFetcher()
        self.feature_generator = FeatureGenerator()
        self.tech_calculator = TechnicalIndicatorCalculator()
        
        # These will be initialized when loading data
        self.data_normalizer = None
        self.data_validator = None
        
        logger.info("RealFeederPlugin initialized with modular components")
    
    def set_params(self, **params):
        """Set plugin parameters."""
        for key, value in params.items():
            if key in self.params:
                self.params[key] = value
                logger.debug(f"Set parameter {key} = {value}")
            else:
                logger.warning(f"Unknown parameter: {key}")
    
    def load_data(self, start_date_time: str, end_date_time: str, **kwargs) -> pd.DataFrame:
        """
        Load and process real market data.
        
        Args:
            start_date_time: Start datetime string (YYYY-MM-DD HH:MM:SS)
            end_date_time: End datetime string (YYYY-MM-DD HH:MM:SS)
            **kwargs: Additional parameters
            
        Returns:
            Processed and normalized DataFrame ready for prediction
        """
        try:
            # Parse datetime strings
            start_date = datetime.strptime(start_date_time, '%Y-%m-%d %H:%M:%S')
            end_date = datetime.strptime(end_date_time, '%Y-%m-%d %H:%M:%S')
            
            # Update parameters from kwargs
            additional_ticks = kwargs.get('additional_previous_ticks', self.params['additional_previous_ticks'])
            
            logger.info(f"Loading real data from {start_date} to {end_date}")
            logger.info(f"Additional previous ticks: {additional_ticks}")
            
            # Initialize normalizer and validator
            self._initialize_components()
            
            # Step 1: Fetch all timeframe data
            hourly_data, data_15m, data_30m = self.data_fetcher.fetch_all_timeframes(start_date, end_date)
            
            if hourly_data.empty:
                logger.error("No hourly data available")
                return pd.DataFrame()
            
            # Step 2: Generate basic features (including ticks)
            feature_data = self.feature_generator.generate_all_features(
                hourly_data, data_15m, data_30m, additional_ticks
            )
            
            # Step 3: Calculate technical indicators
            tech_data = self.tech_calculator.calculate_all_indicators(feature_data)
            
            # Step 4: Normalize the data
            if self.data_normalizer:
                normalized_data = self.data_normalizer.normalize_data(tech_data)
            else:
                logger.warning("No normalizer available, skipping normalization")
                normalized_data = tech_data
            
            # Step 5: Validate the data
            if self.data_validator:
                self._validate_output_data(normalized_data, start_date, end_date)
            
            logger.info(f"Successfully loaded and processed data. Final shape: {normalized_data.shape}")
            return normalized_data
            
        except Exception as e:
            logger.error(f"Error loading real data: {e}")
            raise
    
    def _initialize_components(self):
        """Initialize normalizer and validator components."""
        try:
            # Initialize data normalizer
            normalization_file = self.params.get('use_normalization_json')
            if normalization_file:
                self.data_normalizer = DataNormalizer(normalization_file)
                logger.info("Data normalizer initialized")
            
            # Initialize data validator with reference data
            reference_file = "examples/data/phase_3/normalized_d4.csv"
            try:
                self.data_validator = DataValidator(reference_file)
                logger.info("Data validator initialized with reference data")
            except:
                self.data_validator = DataValidator()
                logger.info("Data validator initialized without reference data")
                
        except Exception as e:
            logger.error(f"Error initializing components: {e}")
    
    def _validate_output_data(self, data: pd.DataFrame, start_date: datetime, end_date: datetime):
        """Validate the final output data."""
        try:
            # Quality validation
            quality_results = self.data_validator.validate_data_quality(data)
            if not quality_results['valid']:
                logger.warning(f"Data quality issues: {quality_results['issues']}")
            
            # Timestamp range validation
            range_results = self.data_validator.validate_timestamp_range(data, start_date, end_date)
            if not range_results['valid']:
                logger.warning(f"Timestamp range issues: {range_results['issues']}")
            
            # Reference data validation (if available)
            if self.data_validator.reference_data is not None:
                tolerance = self.params.get('error_tolerance', 0.001)
                ref_results = self.data_validator.validate_against_reference(data, tolerance)
                if not ref_results['valid']:
                    logger.warning(f"Reference validation issues: {ref_results['issues']}")
                else:
                    logger.info("Data validation against reference passed")
            
            # Normalization validation
            if self.data_normalizer:
                norm_results = self.data_normalizer.validate_normalization(data)
                if not norm_results['valid']:
                    logger.warning(f"Normalization validation issues: {norm_results['issues']}")
                else:
                    logger.info("Normalization validation passed")
            
        except Exception as e:
            logger.error(f"Error validating output data: {e}")
    
    def get_data_columns(self) -> List[str]:
        """
        Get the list of expected data columns.
        
        Returns:
            List of column names that will be in the output data
        """
        # Base columns
        base_columns = ['OPEN', 'HIGH', 'LOW', 'CLOSE', 'S&P500_Close', 'vix_close']
        
        # Tick columns
        additional_ticks = self.params.get('additional_previous_ticks', 50)
        num_ticks = 8 + additional_ticks
        
        tick_columns = []
        for timeframe in ['15m', '30m']:
            for i in range(1, num_ticks + 1):
                tick_columns.append(f'tick_{timeframe}_{i}')
        
        # Technical indicator columns
        tech_columns = self.tech_calculator.get_all_indicator_names()
        
        return base_columns + tick_columns + tech_columns
    
    def get_info(self) -> Dict[str, Any]:
        """Get plugin information."""
        return {
            "name": "RealFeederPlugin",
            "version": "2.0.0",
            "description": "Fetches real market data with technical indicators and multi-timeframe features",
            "parameters": self.params,
            "components": {
                "data_fetcher": "DataFetcher",
                "feature_generator": "FeatureGenerator", 
                "technical_indicators": "TechnicalIndicatorCalculator",
                "data_normalizer": "DataNormalizer" if self.data_normalizer else None,
                "data_validator": "DataValidator" if self.data_validator else None
            },
            "expected_columns": self.get_data_columns()
        }
