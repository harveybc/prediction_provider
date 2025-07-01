#!/usr/bin/env python3
"""
Default Feeder Plugin

This plugin handles data fetching and feeding for the Prediction Provider.
It downloads and processes financial data from various sources based on configuration parameters.
Supports batch data fetching, date filtering, and feature selection.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import json
import os

class DefaultFeederPlugin:
    """
    Default data feeder plugin for fetching financial market data.
    """
    
    # Plugin parameters with default values
    plugin_params = {
        "data_source": "file",  # Options: 'file', 'api', 'database'
        "data_file_path": "data/market_data.csv",
        "api_endpoint": None,
        "api_key": None,
        "batch_size": 32,
        "window_size": 144,
        "time_horizon": 6,
        "target_column": "CLOSE",
        "feature_columns": ["OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"],
        "date_column": "DATE_TIME",
        "fetch_buffer_hours": 24,  # Extra hours to fetch before target datetime
        "data_format": "csv",  # Options: 'csv', 'json', 'parquet'
        "normalize_data": False,
        "fill_missing_data": True,
        "missing_data_method": "forward_fill"  # Options: 'forward_fill', 'interpolate', 'drop'
    }
    
    # Debug variables for monitoring
    plugin_debug_vars = [
        "data_source", "batch_size", "window_size", "time_horizon", 
        "target_column", "date_column"
    ]
    
    def __init__(self, config=None):
        """
        Initialize the feeder plugin.
        
        Args:
            config (dict): Configuration parameters
        """
        self.params = self.plugin_params.copy()
        self.data_cache = {}
        
        if config:
            self.set_params(**config)
    
    def set_params(self, **kwargs):
        """
        Update plugin parameters with provided configuration.
        
        Args:
            **kwargs: Configuration parameters to update
        """
        for key, value in kwargs.items():
            self.params[key] = value
    
    def get_debug_info(self):
        """
        Get debug information for this plugin.
        
        Returns:
            dict: Debug information
        """
        return {var: self.params.get(var) for var in self.plugin_debug_vars}
    
    def add_debug_info(self, debug_info):
        """
        Add debug information to the provided dictionary.
        
        Args:
            debug_info (dict): Dictionary to add debug info to
        """
        debug_info.update(self.get_debug_info())
    
    def fetch_data_for_prediction(self, target_datetime, model_input_shape=None):
        """
        Fetch data required for making a prediction at the specified datetime.
        
        Args:
            target_datetime (str or datetime): Target datetime for prediction
            model_input_shape (tuple): Expected input shape for the model
            
        Returns:
            dict: Dictionary containing fetched data and metadata
        """
        if isinstance(target_datetime, str):
            target_datetime = pd.to_datetime(target_datetime)
        
        batch_size = self.params.get("batch_size", 32)
        window_size = self.params.get("window_size", 144)
        buffer_hours = self.params.get("fetch_buffer_hours", 24)
        
        # Calculate the data range needed
        start_datetime = target_datetime - timedelta(hours=window_size + buffer_hours)
        end_datetime = target_datetime
        
        print(f"Fetching data from {start_datetime} to {end_datetime}")
        
        try:
            # Fetch raw data
            raw_data = self._fetch_raw_data(start_datetime, end_datetime)
            
            # Process and prepare data
            processed_data = self._process_data(raw_data, target_datetime)
            
            # Create windowed data for prediction
            prediction_data = self._create_prediction_windows(processed_data)
            
            return {
                "data": prediction_data,
                "target_datetime": target_datetime,
                "data_shape": prediction_data.shape if hasattr(prediction_data, 'shape') else None,
                "features": self.params.get("feature_columns", []),
                "metadata": {
                    "start_datetime": start_datetime,
                    "end_datetime": end_datetime,
                    "records_fetched": len(raw_data) if raw_data is not None else 0,
                    "records_processed": len(processed_data) if processed_data is not None else 0
                }
            }
            
        except Exception as e:
            raise Exception(f"Failed to fetch data for prediction: {str(e)}")
    
    def _fetch_raw_data(self, start_datetime, end_datetime):
        """
        Fetch raw data from the configured data source.
        
        Args:
            start_datetime (datetime): Start of data range
            end_datetime (datetime): End of data range
            
        Returns:
            pandas.DataFrame: Raw data
        """
        data_source = self.params.get("data_source", "file")
        
        if data_source == "file":
            return self._fetch_from_file(start_datetime, end_datetime)
        elif data_source == "api":
            return self._fetch_from_api(start_datetime, end_datetime)
        elif data_source == "database":
            return self._fetch_from_database(start_datetime, end_datetime)
        else:
            raise ValueError(f"Unsupported data source: {data_source}")
    
    def _fetch_from_file(self, start_datetime, end_datetime):
        """
        Fetch data from a CSV file.
        
        Args:
            start_datetime (datetime): Start of data range
            end_datetime (datetime): End of data range
            
        Returns:
            pandas.DataFrame: Data from file
        """
        file_path = self.params.get("data_file_path")
        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError(f"Data file not found: {file_path}")
        
        # Read the file
        data_format = self.params.get("data_format", "csv").lower()
        
        if data_format == "csv":
            df = pd.read_csv(file_path)
        elif data_format == "json":
            df = pd.read_json(file_path)
        elif data_format == "parquet":
            df = pd.read_parquet(file_path)
        else:
            raise ValueError(f"Unsupported data format: {data_format}")
        
        # Convert date column to datetime
        date_column = self.params.get("date_column", "DATE_TIME")
        if date_column in df.columns:
            df[date_column] = pd.to_datetime(df[date_column])
            
            # Filter by date range
            mask = (df[date_column] >= start_datetime) & (df[date_column] <= end_datetime)
            df = df[mask].copy()
        
        return df
    
    def _fetch_from_api(self, start_datetime, end_datetime):
        """
        Fetch data from an API endpoint.
        
        Args:
            start_datetime (datetime): Start of data range
            end_datetime (datetime): End of data range
            
        Returns:
            pandas.DataFrame: Data from API
        """
        api_endpoint = self.params.get("api_endpoint")
        api_key = self.params.get("api_key")
        
        if not api_endpoint:
            raise ValueError("API endpoint not configured")
        
        # Prepare API request parameters
        params = {
            "start": start_datetime.isoformat(),
            "end": end_datetime.isoformat()
        }
        
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        try:
            response = requests.get(api_endpoint, params=params, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            df = pd.DataFrame(data)
            
            return df
            
        except requests.RequestException as e:
            raise Exception(f"API request failed: {str(e)}")
    
    def _fetch_from_database(self, start_datetime, end_datetime):
        """
        Fetch data from a database.
        
        Args:
            start_datetime (datetime): Start of data range
            end_datetime (datetime): End of data range
            
        Returns:
            pandas.DataFrame: Data from database
        """
        # Placeholder for database implementation
        # This would typically use SQLAlchemy or similar
        raise NotImplementedError("Database data source not yet implemented")
    
    def _process_data(self, raw_data, target_datetime):
        """
        Process and clean the raw data.
        
        Args:
            raw_data (pandas.DataFrame): Raw data
            target_datetime (datetime): Target datetime for prediction
            
        Returns:
            pandas.DataFrame: Processed data
        """
        if raw_data is None or raw_data.empty:
            raise ValueError("No raw data available for processing")
        
        df = raw_data.copy()
        
        # Select required columns
        feature_columns = self.params.get("feature_columns", [])
        date_column = self.params.get("date_column", "DATE_TIME")
        
        # Include date column and feature columns
        required_columns = [date_column] + feature_columns
        available_columns = [col for col in required_columns if col in df.columns]
        
        if not available_columns:
            raise ValueError("No required columns found in data")
        
        df = df[available_columns].copy()
        
        # Handle missing data
        if self.params.get("fill_missing_data", True):
            method = self.params.get("missing_data_method", "forward_fill")
            
            if method == "forward_fill":
                df = df.fillna(method='ffill')
            elif method == "interpolate":
                df = df.interpolate()
            elif method == "drop":
                df = df.dropna()
        
        # Sort by date
        if date_column in df.columns:
            df = df.sort_values(date_column)
        
        # Normalize data if requested
        if self.params.get("normalize_data", False):
            df = self._normalize_data(df)
        
        return df
    
    def _normalize_data(self, df):
        """
        Normalize numerical data.
        
        Args:
            df (pandas.DataFrame): Data to normalize
            
        Returns:
            pandas.DataFrame: Normalized data
        """
        date_column = self.params.get("date_column", "DATE_TIME")
        
        # Identify numerical columns (exclude date column)
        numerical_columns = df.select_dtypes(include=[np.number]).columns
        numerical_columns = [col for col in numerical_columns if col != date_column]
        
        # Min-max normalization
        for col in numerical_columns:
            col_min = df[col].min()
            col_max = df[col].max()
            
            if col_max > col_min:
                df[col] = (df[col] - col_min) / (col_max - col_min)
        
        return df
    
    def _create_prediction_windows(self, processed_data):
        """
        Create windowed data suitable for model prediction.
        
        Args:
            processed_data (pandas.DataFrame): Processed data
            
        Returns:
            numpy.ndarray: Windowed data for prediction
        """
        window_size = self.params.get("window_size", 144)
        feature_columns = self.params.get("feature_columns", [])
        date_column = self.params.get("date_column", "DATE_TIME")
        
        # Get numerical feature data
        feature_data = processed_data[feature_columns].values
        
        if len(feature_data) < window_size:
            raise ValueError(f"Insufficient data: need {window_size} records, got {len(feature_data)}")
        
        # Create the prediction window (most recent data)
        prediction_window = feature_data[-window_size:]
        
        # Reshape for model input (add batch dimension)
        prediction_data = np.expand_dims(prediction_window, axis=0)
        
        return prediction_data
    
    def get_feature_info(self):
        """
        Get information about available features.
        
        Returns:
            dict: Feature information
        """
        return {
            "feature_columns": self.params.get("feature_columns", []),
            "target_column": self.params.get("target_column", "CLOSE"),
            "date_column": self.params.get("date_column", "DATE_TIME"),
            "window_size": self.params.get("window_size", 144),
            "batch_size": self.params.get("batch_size", 32)
        }
