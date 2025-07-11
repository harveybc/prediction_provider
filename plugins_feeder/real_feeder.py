#!/usr/bin/env python3
"""
Real Feeder Plugin - Fully Isolated and Configurable

This plugin provides complete replicability across different applications.
All processing parameters are contained in the config to ensure identical results.

Features:
- Fetches EURUSD hourly HLOC data
- Fetches S&P500 and VIX hourly close data  
- Generates multi-timeframe tick features (15m, 30m)
- Calculates technical indicators matching feature-eng repo
- Generates STL features (trend, seasonal, residual, wavelets, MTM)
- Normalizes data using training data min/max values
- Validates against historical data

The plugin is fully self-contained and can be used in any application
by simply passing the complete configuration parameters.
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
from .stl_feature_generator import STLFeatureGenerator

logger = logging.getLogger(__name__)

class RealFeederPlugin:
    """
    Real market data feeder plugin - Fully Isolated and Configurable.
    
    This plugin is designed for perfect replicability across different applications.
    All configuration is explicit and the plugin is completely self-contained.
    """
    
    # Complete default configuration - all parameters needed for replicability
    DEFAULT_CONFIG = {
        # === Data Source Configuration ===
        "instrument": "EURUSD=X",
        "correlated_instruments": ["^GSPC", "^VIX"],
        
        # === Processing Configuration ===
        "n_batches": 1,
        "batch_size": 256,
        "window_size": 256,
        "target_column": "CLOSE",
        "additional_previous_ticks": 0,
        "error_tolerance": 0.001,
        
        # === Normalization Configuration ===
        "use_normalization_json": "examples/data/phase_3/phase_3_debug_out.json",
        "normalize_features": True,
        
        # === STL Feature Generation Configuration ===
        "use_stl": True,
        "stl_period": 24,
        "stl_window": 49,  # 2 * stl_period + 1
        "stl_trend": 25,   # Calculated based on period and window
        
        # === Wavelet Configuration ===
        "use_wavelets": True,
        "wavelet_name": "db4",
        "wavelet_levels": 2,
        "wavelet_mode": "symmetric",
        
        # === MTM Configuration ===
        "use_multi_tapper": True,
        "mtm_window_len": 168,
        "mtm_step": 1,
        "mtm_time_bandwidth": 5.0,
        "mtm_num_tapers": None,
        "mtm_freq_bands": [(0, 0.01), (0.01, 0.06), (0.06, 0.2), (0.2, 0.5)],
        
        # === Technical Indicators Configuration ===
        "use_technical_indicators": True,
        "preserve_base_features": True,
        "preserve_ohlc": True,  # Keep OPEN, HIGH, LOW (CLOSE becomes log_return)
        
        # === Feature Output Configuration ===
        "expected_feature_count": 54,
        "expected_stl_features": 11,
        "expected_technical_indicators": 15,
        "expected_tick_features": 16,
        
        # === Validation Configuration ===
        "validate_feature_count": True,
        "validate_feature_names": True,
        "strict_validation": True,
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the real feeder plugin with plugin-specific parameters.
        
        Args:
            config: Configuration dictionary to merge with plugin defaults.
                   If None, uses DEFAULT_CONFIG. Main app should pass merged config.
        """
        # Start with plugin-specific default parameters
        self.params = self.DEFAULT_CONFIG.copy()
        
        # Update with provided configuration (merged by main app)
        if config:
            self.params.update(config)
        
        # Initialize core components with final parameters
        self._initialize_components()
        
        # Log the final parameters for replicability
        logger.info("RealFeederPlugin initialized with final parameters")
        logger.debug(f"Final params: {json.dumps(self.params, indent=2)}")
    
    def _initialize_components(self):
        """Initialize all components with final parameters."""
        self.data_fetcher = DataFetcher()
        self.feature_generator = FeatureGenerator()
        self.tech_calculator = TechnicalIndicatorCalculator()
        
        # Initialize STL generator with specific parameters
        stl_config = {
            "use_stl": self.params["use_stl"],
            "stl_period": self.params["stl_period"],
            "stl_window": self.params["stl_window"],
            "stl_trend": self.params["stl_trend"],
            "use_wavelets": self.params["use_wavelets"],
            "wavelet_name": self.params["wavelet_name"],
            "wavelet_levels": self.params["wavelet_levels"],
            "wavelet_mode": self.params["wavelet_mode"],
            "use_multi_tapper": self.params["use_multi_tapper"],
            "mtm_window_len": self.params["mtm_window_len"],
            "mtm_step": self.params["mtm_step"],
            "mtm_time_bandwidth": self.params["mtm_time_bandwidth"],
            "mtm_num_tapers": self.params["mtm_num_tapers"],
            "mtm_freq_bands": self.params["mtm_freq_bands"],
            "normalize_features": self.params["normalize_features"],
        }
        
        self.stl_generator = STLFeatureGenerator(config=stl_config)
        
        # These will be initialized when loading data
        self.data_normalizer = None
        self.data_validator = None
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get the final parameters used by this plugin.
        
        This can be saved and used in other applications to ensure perfect replicability.
        Other apps should pass these exact parameters to achieve identical results.
        
        Returns:
            Final plugin parameters dictionary
        """
        return self.params.copy()
    
    def save_config(self, filepath: str):
        """
        Save the final plugin parameters to a JSON file.
        
        Args:
            filepath: Path to save the parameters JSON file
        """
        with open(filepath, 'w') as f:
            json.dump(self.params, f, indent=2)
        logger.info(f"Plugin parameters saved to {filepath}")
    
    @classmethod
    def from_config_file(cls, filepath: str) -> 'RealFeederPlugin':
        """
        Create a RealFeederPlugin instance from a saved parameters file.
        
        This ensures perfect replicability when using the plugin in other apps.
        
        Args:
            filepath: Path to the saved parameters JSON file
            
        Returns:
            RealFeederPlugin instance with loaded parameters
        """
        with open(filepath, 'r') as f:
            params = json.load(f)
        return cls(config=params)
    
    def load_data(self, start_date_time: str, end_date_time: str, **kwargs) -> pd.DataFrame:
        """
        Load and process real market data using the complete configuration.
        
        Args:
            start_date_time: Start datetime string (YYYY-MM-DD HH:MM:SS)
            end_date_time: End datetime string (YYYY-MM-DD HH:MM:SS)
            **kwargs: Additional parameters (will override config values)
            
        Returns:
            Processed and normalized DataFrame ready for prediction
        """
        try:
            # Parse datetime strings
            start_date = datetime.strptime(start_date_time, '%Y-%m-%d %H:%M:%S')
            end_date = datetime.strptime(end_date_time, '%Y-%m-%d %H:%M:%S')
            
            # Get parameters from final params (can be overridden by kwargs)
            additional_ticks = kwargs.get('additional_previous_ticks', self.params['additional_previous_ticks'])
            
            logger.info(f"Loading real data from {start_date} to {end_date}")
            logger.info(f"Using parameters: {self.params['instrument']}, STL: {self.params['use_stl']}")
            logger.info(f"Additional previous ticks: {additional_ticks}")
            
            # Initialize components if needed
            if self.data_normalizer is None:
                self._initialize_normalizer_and_validator()
            
            # Step 1: Fetch all timeframe data using configured instruments
            hourly_data, data_15m, data_30m = self.data_fetcher.fetch_all_timeframes(
                start_date, end_date, 
                instrument=self.params['instrument'],
                correlated_instruments=self.params['correlated_instruments']
            )
            
            if hourly_data.empty:
                logger.error("No hourly data available")
                return pd.DataFrame()
            
            # Step 2: Generate basic features (including ticks)
            feature_data = self.feature_generator.generate_all_features(
                hourly_data, data_15m, data_30m, additional_ticks
            )
            
            # Step 3: Calculate technical indicators
            logger.info(f"Feature data shape before tech indicators: {feature_data.shape if feature_data is not None else 'None'}")
            logger.info(f"Feature data columns: {list(feature_data.columns) if feature_data is not None else 'None'}")
            
            if self.params['use_technical_indicators']:
                tech_data = self.tech_calculator.calculate_all_indicators(feature_data)
            else:
                tech_data = feature_data.copy()
            
            # Step 4: Generate STL features if enabled
            if (self.params['use_stl'] and feature_data is not None and 
                not feature_data.empty and 'CLOSE' in feature_data.columns):
                
                logger.info("Generating STL features from CLOSE column...")
                
                # Use the CLOSE column to generate STL features
                stl_features = self.stl_generator.generate_stl_features(feature_data[['CLOSE']])
                
                if stl_features is not None and not stl_features.empty:
                    # Align STL features with the technical data
                    base_length = len(tech_data)
                    stl_length = len(stl_features)
                    
                    # Determine the overlap length
                    min_length = min(base_length, stl_length)
                    
                    # Trim both datasets to the same length (from the end)
                    tech_data = tech_data.iloc[-min_length:].copy()
                    stl_features = stl_features.iloc[-min_length:].copy()
                    
                    # Add STL features to the dataset
                    for col in stl_features.columns:
                        tech_data[col] = stl_features[col].values
                    
                    logger.info(f"Added {len(stl_features.columns)} STL features. Dataset shape: {tech_data.shape}")
                    
                    # Remove CLOSE column as it's replaced by log_return from STL
                    # Keep OPEN, HIGH, LOW as per parameters
                    if self.params['preserve_ohlc'] and 'CLOSE' in tech_data.columns:
                        tech_data = tech_data.drop('CLOSE', axis=1)
                        logger.info("Removed original CLOSE column (replaced by log_return from STL)")
                else:
                    logger.warning("No STL features generated")
            else:
                if not self.params['use_stl']:
                    logger.info("STL feature generation disabled by parameters")
                else:
                    logger.warning("Cannot generate STL features: missing CLOSE column or empty data")
            
            # Step 5: Validate feature count if configured
            if self.params['validate_feature_count']:
                expected_count = self.params['expected_feature_count']
                actual_count = len(tech_data.columns)
                
                if actual_count != expected_count:
                    logger.error(f"Feature count mismatch: expected {expected_count}, got {actual_count}")
                    logger.error(f"Features: {list(tech_data.columns)}")
                    if self.params['strict_validation']:
                        raise ValueError(f"Feature count validation failed: {actual_count} != {expected_count}")
                else:
                    logger.info(f"✅ Feature count validation passed: {actual_count} features")
            
            # Step 6: Normalize the data if configured
            if self.params['normalize_features'] and self.data_normalizer:
                normalized_data = self.data_normalizer.normalize_data(tech_data)
            else:
                if not self.params['normalize_features']:
                    logger.info("Data normalization disabled by parameters")
                else:
                    logger.warning("No normalizer available, skipping normalization")
                normalized_data = tech_data
            
            # Step 6: Validate the data
            if self.data_validator:
                self._validate_output_data(normalized_data, start_date, end_date)
            
            logger.info(f"Successfully loaded and processed data. Final shape: {normalized_data.shape}")
            return normalized_data
            
        except Exception as e:
            logger.error(f"Error loading real data: {e}")
            raise
    
    def _initialize_normalizer_and_validator(self):
        """Initialize normalizer and validator components using final parameters."""
        try:
            # Initialize data normalizer
            normalization_file = self.params.get('use_normalization_json')
            if normalization_file:
                self.data_normalizer = DataNormalizer(normalization_file)
                logger.info(f"Data normalizer initialized with {normalization_file}")
            
            # Initialize data validator with reference data
            reference_file = "examples/data/phase_3/normalized_d4.csv"
            try:
                self.data_validator = DataValidator(reference_file)
                logger.info("Data validator initialized with reference data")
            except:
                self.data_validator = DataValidator()
                logger.info("Data validator initialized without reference data")
                
        except Exception as e:
            logger.error(f"Error initializing normalizer and validator: {e}")
    
    def _validate_output_data(self, data: pd.DataFrame, start_date: datetime, end_date: datetime):
        """Validate the final output data using final parameters."""
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
    
    def get_expected_features(self) -> List[str]:
        """
        Get the list of expected feature names based on final parameters.
        
        Returns:
            List of feature names that will be generated by this plugin
        """
        features = []
        
        # Base features (OHLC, technical indicators, tick features, etc.)
        if self.params['preserve_base_features']:
            base_features = [
                'RSI', 'MACD', 'MACD_Histogram', 'MACD_Signal', 'EMA', 
                'Stochastic_%K', 'Stochastic_%D', 'ADX', 'DI+', 'DI-', 'ATR', 'CCI', 
                'WilliamsR', 'Momentum', 'ROC', 'S&P500_Close', 'vix_close'
            ]
            features.extend(base_features)
        
        # OHLC features (OPEN, HIGH, LOW, CLOSE becomes log_return)
        if self.params['preserve_ohlc']:
            features.extend(['OPEN', 'HIGH', 'LOW'])
        
        # Tick features
        tick_features = []
        for timeframe in ['15m', '30m']:
            for i in range(1, 9):  # 8 ticks each
                tick_features.append(f'CLOSE_{timeframe}_tick_{i}')
        features.extend(tick_features)
        
        # Additional base features
        features.extend(['BC-BO', 'BH-BL', 'BH-BO', 'BO-BL', 'day_of_month', 'hour_of_day', 'day_of_week'])
        
        # STL features
        if self.params['use_stl']:
            stl_features = ['log_return']  # Replaces CLOSE
            
            # STL decomposition features
            stl_features.extend(['stl_trend', 'stl_seasonal', 'stl_resid'])
            
            # Wavelet features
            if self.params['use_wavelets']:
                for level in range(1, self.params['wavelet_levels'] + 1):
                    stl_features.append(f'wav_detail_L{level}')
                stl_features.append(f'wav_approx_L{self.params["wavelet_levels"]}')
            
            # MTM features
            if self.params['use_multi_tapper']:
                for i, band in enumerate(self.params['mtm_freq_bands']):
                    stl_features.append(f'mtm_band_{i+1}')
            
            features.extend(stl_features)
        
        return features
    
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
                "stl_feature_generator": "STLFeatureGenerator",
                "data_normalizer": "DataNormalizer" if self.data_normalizer else None,
                "data_validator": "DataValidator" if self.data_validator else None
            },
            "expected_features": self.get_expected_features()
        }
