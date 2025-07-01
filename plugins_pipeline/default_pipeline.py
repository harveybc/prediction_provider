#!/usr/bin/env python3
"""
Default Pipeline Plugin

This plugin orchestrates the prediction system components and manages
the prediction service infrastructure. It coordinates between the feeder,
predictor, and endpoints to provide a unified prediction service.
"""

import time
from datetime import datetime

class DefaultPipelinePlugin:
    """
    Default pipeline plugin for coordinating prediction system components.
    """
    
    # Plugin parameters with default values
    plugin_params = {
        "pipeline_enabled": True,
        "max_prediction_threads": 10,
        "prediction_timeout": 300,  # seconds
        "cache_predictions": False,
        "cache_duration": 3600,  # seconds
        "enable_logging": True,
        "log_level": "INFO"
    }
    
    # Debug variables for monitoring
    plugin_debug_vars = [
        "pipeline_enabled", "max_prediction_threads", "prediction_timeout",
        "cache_predictions", "enable_logging"
    ]
    
    def __init__(self, config=None):
        """
        Initialize the pipeline plugin.
        
        Args:
            config (dict): Configuration parameters
        """
        self.params = self.plugin_params.copy()
        self.predictor_plugin = None
        self.feeder_plugin = None
        self.active_predictions = {}
        self.prediction_cache = {}
        
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
        debug_info = {var: self.params.get(var) for var in self.plugin_debug_vars}
        debug_info.update({
            "active_predictions": len(self.active_predictions),
            "cached_predictions": len(self.prediction_cache),
            "predictor_loaded": self.predictor_plugin is not None,
            "feeder_loaded": self.feeder_plugin is not None
        })
        return debug_info
    
    def add_debug_info(self, debug_info):
        """
        Add debug information to the provided dictionary.
        
        Args:
            debug_info (dict): Dictionary to add debug info to
        """
        debug_info.update(self.get_debug_info())
    
    def initialize_prediction_system(self, config, predictor_plugin, feeder_plugin):
        """
        Initialize the prediction system with the provided plugins.
        
        Args:
            config (dict): System configuration
            predictor_plugin: Predictor plugin instance
            feeder_plugin: Feeder plugin instance
        """
        print("Initializing prediction system...")
        
        self.predictor_plugin = predictor_plugin
        self.feeder_plugin = feeder_plugin
        
        # Configure components
        if self.predictor_plugin:
            self.predictor_plugin.set_params(**config)
            print("Predictor plugin configured")
        
        if self.feeder_plugin:
            self.feeder_plugin.set_params(**config)
            print("Feeder plugin configured")
        
        # Validate system readiness
        if self._validate_system():
            print("Prediction system initialized successfully")
        else:
            print("Warning: Prediction system initialization incomplete")
    
    def _validate_system(self):
        """
        Validate that all required components are available and configured.
        
        Returns:
            bool: True if system is ready, False otherwise
        """
        if not self.params.get("pipeline_enabled", True):
            print("Pipeline is disabled")
            return False
        
        if not self.predictor_plugin:
            print("Predictor plugin not available")
            return False
        
        if not self.feeder_plugin:
            print("Feeder plugin not available")
            return False
        
        return True
    
    def process_prediction_request(self, request_data):
        """
        Process a prediction request through the pipeline.
        
        Args:
            request_data (dict): Prediction request data
            
        Returns:
            dict: Prediction results
        """
        if not self._validate_system():
            raise RuntimeError("Prediction system not properly initialized")
        
        start_time = time.time()
        request_id = request_data.get('id', 'unknown')
        
        try:
            # Track active prediction
            self.active_predictions[request_id] = {
                'start_time': start_time,
                'status': 'processing'
            }
            
            # Check cache if enabled
            if self.params.get("cache_predictions", False):
                cached_result = self._check_prediction_cache(request_data)
                if cached_result:
                    print(f"Returning cached prediction for request {request_id}")
                    return cached_result
            
            # Load model
            model_path = request_data.get('model_path')
            if not self.predictor_plugin.load_model(model_path):
                raise ValueError(f"Failed to load model: {model_path}")
            
            # Fetch data
            target_datetime = request_data.get('target_datetime')
            data_result = self.feeder_plugin.fetch_data_for_prediction(target_datetime)
            
            if not data_result or data_result.get('data') is None:
                raise ValueError("Failed to fetch required data")
            
            # Make prediction
            prediction_data = data_result['data']
            predictions, uncertainties = self.predictor_plugin.predict_with_uncertainty(prediction_data)
            
            # Prepare results
            results = {
                'predictions': predictions.tolist() if hasattr(predictions, 'tolist') else predictions,
                'uncertainties': uncertainties.tolist() if hasattr(uncertainties, 'tolist') else uncertainties,
                'target_datetime': target_datetime,
                'model_path': model_path,
                'processing_time': time.time() - start_time,
                'data_metadata': data_result.get('metadata', {}),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Cache results if enabled
            if self.params.get("cache_predictions", False):
                self._cache_prediction(request_data, results)
            
            return results
            
        finally:
            # Clean up tracking
            if request_id in self.active_predictions:
                del self.active_predictions[request_id]
    
    def _check_prediction_cache(self, request_data):
        """
        Check if a prediction is available in cache.
        
        Args:
            request_data (dict): Prediction request data
            
        Returns:
            dict or None: Cached prediction results or None
        """
        cache_key = self._generate_cache_key(request_data)
        
        if cache_key in self.prediction_cache:
            cached_entry = self.prediction_cache[cache_key]
            
            # Check if cache entry is still valid
            cache_duration = self.params.get("cache_duration", 3600)
            if time.time() - cached_entry['timestamp'] < cache_duration:
                return cached_entry['results']
            else:
                # Remove expired entry
                del self.prediction_cache[cache_key]
        
        return None
    
    def _cache_prediction(self, request_data, results):
        """
        Cache prediction results.
        
        Args:
            request_data (dict): Prediction request data
            results (dict): Prediction results
        """
        cache_key = self._generate_cache_key(request_data)
        
        self.prediction_cache[cache_key] = {
            'results': results,
            'timestamp': time.time()
        }
        
        # Limit cache size to prevent memory issues
        max_cache_size = 100
        if len(self.prediction_cache) > max_cache_size:
            # Remove oldest entries
            sorted_cache = sorted(
                self.prediction_cache.items(),
                key=lambda x: x[1]['timestamp']
            )
            
            for key, _ in sorted_cache[:10]:  # Remove 10 oldest
                del self.prediction_cache[key]
    
    def _generate_cache_key(self, request_data):
        """
        Generate a cache key for a prediction request.
        
        Args:
            request_data (dict): Prediction request data
            
        Returns:
            str: Cache key
        """
        import hashlib
        import json
        
        # Create a deterministic key based on request parameters
        key_data = {
            'model_path': request_data.get('model_path'),
            'target_datetime': request_data.get('target_datetime'),
            'batch_size': request_data.get('batch_size'),
            'features': request_data.get('features')
        }
        
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get_system_status(self):
        """
        Get the current status of the prediction system.
        
        Returns:
            dict: System status information
        """
        return {
            'pipeline_enabled': self.params.get("pipeline_enabled", True),
            'active_predictions': len(self.active_predictions),
            'cached_predictions': len(self.prediction_cache),
            'max_prediction_threads': self.params.get("max_prediction_threads", 10),
            'predictor_available': self.predictor_plugin is not None,
            'feeder_available': self.feeder_plugin is not None,
            'system_ready': self._validate_system()
        }
    
    def cleanup(self):
        """
        Cleanup pipeline resources.
        """
        self.active_predictions.clear()
        self.prediction_cache.clear()
        print("Pipeline cleanup completed")
