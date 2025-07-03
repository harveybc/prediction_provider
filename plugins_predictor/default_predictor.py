#!/usr/bin/env python3
"""
Default Predictor Plugin

This plugin handles model loading, prediction, and evaluation for the Prediction Provider.
It supports loading Keras models and making predictions with uncertainty estimation.
"""

import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow import keras
import os
import json
from datetime import datetime

class DefaultPredictorPlugin:
    """
    Default predictor plugin for loading models and making predictions.
    """
    
    # Plugin parameters with default values
    plugin_params = {
        "model_path": None,
        "normalization_params_path": None,  # Path to normalization params JSON
        "model_type": "keras",  # Options: 'keras', 'sklearn', 'pytorch'
        "prediction_horizon": 6,
        "mc_samples": 100,  # Monte Carlo samples for uncertainty estimation
        "batch_size": 32,
        "use_gpu": True,
        "gpu_memory_limit": None,  # MB, None for no limit
        "enable_mixed_precision": False,
        "model_cache_size": 5,  # Number of models to keep in cache
        "prediction_confidence_level": 0.95,
        "prediction_target_column": "close_price" # The column to be predicted and de-normalized
    }
    
    # Debug variables for monitoring
    plugin_debug_vars = [
        "model_path", "model_type", "prediction_horizon", 
        "mc_samples", "batch_size", "use_gpu", "normalization_params_path"
    ]
    
    def __init__(self, config=None):
        """
        Initialize the predictor plugin.
        
        Args:
            config (dict): Configuration parameters
        """
        self.params = self.plugin_params.copy()
        self.model = None
        self.model_cache = {}
        self.model_metadata = {}
        self.normalization_params = None
        
        if config:
            self.set_params(**config)
        
        # Configure TensorFlow
        self._configure_tensorflow()
    
    def set_params(self, **kwargs):
        """
        Update plugin parameters with provided configuration.
        
        Args:
            **kwargs: Configuration parameters to update
        """
        for key, value in kwargs.items():
            self.params[key] = value
        
        # Reload normalization params if the path changes
        if 'normalization_params_path' in kwargs:
            self._load_normalization_params()
    
    def get_debug_info(self):
        """
        Get debug information for this plugin.
        
        Returns:
            dict: Debug information
        """
        debug_info = {var: self.params.get(var) for var in self.plugin_debug_vars}
        
        # Add model information if available
        if self.model is not None:
            debug_info["model_loaded"] = True
            debug_info["model_input_shape"] = self.model.input_shape if hasattr(self.model, 'input_shape') else None
            debug_info["model_output_shape"] = self.model.output_shape if hasattr(self.model, 'output_shape') else None
        else:
            debug_info["model_loaded"] = False
        
        return debug_info
    
    def add_debug_info(self, debug_info):
        """
        Add debug information to the provided dictionary.
        
        Args:
            debug_info (dict): Dictionary to add debug info to
        """
        debug_info.update(self.get_debug_info())
    
    def _configure_tensorflow(self):
        """
        Configure TensorFlow settings based on plugin parameters.
        """
        # Configure GPU usage
        if self.params.get("use_gpu", True):
            gpus = tf.config.experimental.list_physical_devices('GPU')
            if gpus:
                try:
                    # Enable memory growth or set memory limit
                    for gpu in gpus:
                        if self.params.get("gpu_memory_limit"):
                            tf.config.experimental.set_memory_growth(gpu, True)
                            tf.config.experimental.set_virtual_device_configuration(
                                gpu,
                                [tf.config.experimental.VirtualDeviceConfiguration(
                                    memory_limit=self.params["gpu_memory_limit"]
                                )]
                            )
                        else:
                            tf.config.experimental.set_memory_growth(gpu, True)
                except RuntimeError as e:
                    print(f"GPU configuration error: {e}")
        
        # Configure mixed precision if enabled
        if self.params.get("enable_mixed_precision", False):
            policy = tf.keras.mixed_precision.Policy('mixed_float16')
            tf.keras.mixed_precision.set_global_policy(policy)

    def _load_normalization_params(self):
        """
        Load normalization parameters from the specified JSON file.
        """
        path = self.params.get("normalization_params_path")
        if not path or not os.path.exists(path):
            print(f"Warning: Normalization params file not found at {path}. De-normalization will be skipped.")
            self.normalization_params = None
            return

        try:
            with open(path, 'r') as f:
                self.normalization_params = json.load(f)
            print(f"Normalization parameters loaded successfully from {path}")
        except Exception as e:
            print(f"Failed to load or parse normalization parameters from {path}: {e}")
            self.normalization_params = None

    def load_model(self, model_path=None):
        """
        Load a trained model from file.
        
        Args:
            model_path (str): Path to the model file
            
        Returns:
            bool: True if model loaded successfully, False otherwise
        """
        if model_path is None:
            model_path = self.params.get("model_path")
        
        if not model_path:
            raise ValueError("No model path specified")
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        # Check if model is already in cache
        if model_path in self.model_cache:
            self.model = self.model_cache[model_path]
            print(f"Model loaded from cache: {model_path}")
            return True
        
        try:
            model_type = self.params.get("model_type", "keras")
            
            if model_type == "keras":
                self.model = self._load_keras_model(model_path)
            elif model_type == "sklearn":
                self.model = self._load_sklearn_model(model_path)
            elif model_type == "pytorch":
                self.model = self._load_pytorch_model(model_path)
            else:
                raise ValueError(f"Unsupported model type: {model_type}")
            
            # Cache the model
            self._cache_model(model_path, self.model)
            
            # Load model metadata if available
            self._load_model_metadata(model_path)
            
            # Load normalization parameters
            self._load_normalization_params()

            print(f"Model loaded successfully: {model_path}")
            return True
            
        except Exception as e:
            print(f"Failed to load model from {model_path}: {str(e)}")
            self.model = None
            return False
    
    def _load_keras_model(self, model_path):
        """
        Load a Keras model.
        
        Args:
            model_path (str): Path to the Keras model
            
        Returns:
            keras.Model: Loaded Keras model
        """
        # Custom objects for loading models with custom layers/functions
        custom_objects = {
            # Add any custom objects needed for your models
        }
        
        model = keras.models.load_model(model_path, custom_objects=custom_objects)
        return model
    
    def _load_sklearn_model(self, model_path):
        """
        Load a scikit-learn model.
        
        Args:
            model_path (str): Path to the sklearn model
            
        Returns:
            object: Loaded sklearn model
        """
        import joblib
        model = joblib.load(model_path)
        return model
    
    def _load_pytorch_model(self, model_path):
        """
        Load a PyTorch model.
        
        Args:
            model_path (str): Path to the PyTorch model
            
        Returns:
            object: Loaded PyTorch model
        """
        # Placeholder for PyTorch model loading
        raise NotImplementedError("PyTorch model loading not yet implemented")
    
    def _cache_model(self, model_path, model):
        """
        Cache a loaded model.
        
        Args:
            model_path (str): Path to the model
            model: Loaded model object
        """
        cache_size = self.params.get("model_cache_size", 5)
        
        # Remove oldest model if cache is full
        if len(self.model_cache) >= cache_size:
            oldest_key = next(iter(self.model_cache))
            del self.model_cache[oldest_key]
        
        self.model_cache[model_path] = model
    
    def _load_model_metadata(self, model_path):
        """
        Load model metadata if available.
        
        Args:
            model_path (str): Path to the model file
        """
        metadata_path = model_path.replace('.keras', '_metadata.json').replace('.h5', '_metadata.json')
        
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r') as f:
                    self.model_metadata = json.load(f)
                print(f"Model metadata loaded: {metadata_path}")
            except Exception as e:
                print(f"Failed to load model metadata: {e}")
                self.model_metadata = {}
        else:
            self.model_metadata = {}
    
    def predict(self, input_data):
        """
        Make predictions using the loaded model.
        
        Args:
            input_data (numpy.ndarray): Input data for prediction
            
        Returns:
            numpy.ndarray: Predictions
        """
        if self.model is None:
            raise ValueError("No model loaded. Call load_model() first.")
        
        try:
            # Ensure input data is properly shaped
            if isinstance(input_data, pd.DataFrame):
                input_data = input_data.values
            
            input_data = np.array(input_data)
            
            # Make predictions
            predictions = self.model.predict(input_data, batch_size=self.params.get("batch_size", 32))
            
            return predictions
            
        except Exception as e:
            raise Exception(f"Prediction failed: {str(e)}")

    def _denormalize(self, predictions, uncertainties):
        """
        De-normalize predictions and uncertainties.
        """
        target_col = self.params.get("prediction_target_column", "close_price")

        if self.normalization_params is None or target_col not in self.normalization_params:
            print("Warning: Normalization parameters not available for target column. Skipping de-normalization.")
            return predictions, uncertainties

        stats = self.normalization_params[target_col]
        mean = stats.get('mean', 0)
        std = stats.get('std', 1)

        if std == 0:
            print("Warning: Standard deviation is zero. Cannot de-normalize.")
            return predictions, uncertainties

        # De-normalize predictions: value * std + mean
        denormalized_preds = (predictions * std) + mean

        # De-normalize uncertainties: value * std
        denormalized_uncerts = uncertainties * std

        return denormalized_preds, denormalized_uncerts

    def predict_with_uncertainty(self, input_data, mc_samples=None):
        """
        Make predictions with uncertainty estimation using Monte Carlo dropout.
        
        Args:
            input_data (numpy.ndarray): Input data for prediction
            mc_samples (int): Number of Monte Carlo samples
            
        Returns:
            tuple: (predictions, uncertainties)
        """
        if self.model is None:
            raise ValueError("No model loaded. Call load_model() first.")
        
        if mc_samples is None:
            mc_samples = self.params.get("mc_samples", 100)
        
        try:
            # Ensure input data is properly shaped
            if isinstance(input_data, pd.DataFrame):
                # Ensure columns are in the correct order if metadata is available
                if self.model_metadata and 'feature_columns' in self.model_metadata:
                    input_data = input_data[self.model_metadata['feature_columns']]
                input_data = input_data.values

            input_data = np.array(input_data)
            
            # Store predictions from multiple forward passes
            predictions_list = []
            
            # Enable dropout during inference for uncertainty estimation
            for _ in range(mc_samples):
                # For Keras models, use training=True to enable dropout
                if hasattr(self.model, 'predict'):
                    if hasattr(self.model, '__call__'):
                        # Call model with training=True to enable dropout
                        pred = self.model(input_data, training=True)
                        if hasattr(pred, 'numpy'):
                            pred = pred.numpy()
                    else:
                        pred = self.model.predict(input_data, batch_size=self.params.get("batch_size", 32))
                else:
                    pred = self.model.predict(input_data)
                
                predictions_list.append(pred)
            
            # Convert to numpy array
            predictions_array = np.array(predictions_list)
            
            # Calculate mean and standard deviation
            mean_predictions = np.mean(predictions_array, axis=0)
            uncertainty_estimates = np.std(predictions_array, axis=0)

            # De-normalize the results
            denormalized_preds, denormalized_uncerts = self._denormalize(mean_predictions, uncertainty_estimates)

            # Format the output
            output = {
                "prediction_timestamp": datetime.utcnow().isoformat(),
                "prediction": denormalized_preds.tolist(),
                "uncertainty": denormalized_uncerts.tolist(),
                "metadata": {
                    "model_path": self.params.get("model_path"),
                    "prediction_horizon": self.params.get("prediction_horizon"),
                    "mc_samples": mc_samples,
                    "de_normalized": self.normalization_params is not None
                }
            }
            
            return output
            
        except Exception as e:
            # Fallback to regular prediction if uncertainty estimation fails
            print(f"Uncertainty estimation failed, using regular prediction: {str(e)}")
            predictions = self.predict(input_data)
            uncertainties = np.zeros_like(predictions)

            denormalized_preds, denormalized_uncerts = self._denormalize(predictions, uncertainties)
            
            output = {
                "prediction_timestamp": datetime.utcnow().isoformat(),
                "prediction": denormalized_preds.tolist(),
                "uncertainty": denormalized_uncerts.tolist(),
                "metadata": {
                    "model_path": self.params.get("model_path"),
                    "prediction_horizon": self.params.get("prediction_horizon"),
                    "mc_samples": 0,
                    "error": f"Uncertainty estimation failed: {str(e)}",
                    "de_normalized": self.normalization_params is not None
                }
            }
            return output
    
    def get_model_info(self):
        """
        Get information about the loaded model.
        
        Returns:
            dict: Model information
        """
        if self.model is None:
            return {"model_loaded": False}
        
        info = {
            "model_loaded": True,
            "model_type": self.params.get("model_type", "keras"),
            "model_path": self.params.get("model_path"),
            "prediction_horizon": self.params.get("prediction_horizon", 6),
            "metadata": self.model_metadata
        }
        
        # Add model-specific information
        if hasattr(self.model, 'input_shape'):
            info["input_shape"] = self.model.input_shape
        if hasattr(self.model, 'output_shape'):
            info["output_shape"] = self.model.output_shape
        if hasattr(self.model, 'count_params'):
            info["total_params"] = self.model.count_params()
        
        return info
    
    def validate_input_shape(self, input_data):
        """
        Validate that input data matches expected model input shape.
        
        Args:
            input_data (numpy.ndarray): Input data to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        if self.model is None:
            return False
        
        if not hasattr(self.model, 'input_shape'):
            return True  # Cannot validate, assume it's okay
        
        expected_shape = self.model.input_shape
        actual_shape = input_data.shape
        
        # Check if shapes are compatible (ignoring batch dimension)
        if len(expected_shape) != len(actual_shape):
            return False
        
        for i in range(1, len(expected_shape)):  # Skip batch dimension
            if expected_shape[i] is not None and expected_shape[i] != actual_shape[i]:
                return False
        
        return True
