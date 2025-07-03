# config.py
# Configuration file for the Prediction Provider system
# This file contains ALL configuration parameters used by the system plugins

DEFAULT_VALUES = {
    # --- Core Plugin Configuration ---
    "core_plugin": "default_core",
    "host": "127.0.0.1",
    "port": 8000,
    
    # --- Endpoints Plugin Configuration ---
    "endpoints_plugin": "default_endpoints",
    "endpoints_host": "0.0.0.0",
    "endpoints_port": 5000,
    "endpoints_debug": False,
    "endpoints_db_path": "prediction_provider.db",
    
    # --- Feeder Plugin Configuration ---
    "feeder_plugin": "default_feeder",
    "instrument": "MSFT",
    "correlated_instruments": [],
    "n_batches": 1,
    "batch_size": 256,
    "window_size": 256,
    "use_normalization_json": None,
    "target_column": "Close",
    
    # --- Predictor Plugin Configuration ---
    "predictor_plugin": "default_predictor",
    "model_path": None,
    "normalization_params_path": None,
    "model_type": "keras",
    "prediction_horizon": 6,
    "mc_samples": 100,
    "use_gpu": True,
    "gpu_memory_limit": None,
    "enable_mixed_precision": False,
    "model_cache_size": 5,
    "prediction_confidence_level": 0.95,
    "prediction_target_column": "close_price",
    
    # --- Pipeline Plugin Configuration ---
    "pipeline_plugin": "default_pipeline",
    "pipeline_enabled": True,
    "prediction_interval": 300,
    "pipeline_db_path": "prediction_provider.db",
    "enable_logging": True,
    "log_level": "INFO",
    
    # --- Database Configuration ---
    "database_url": "sqlite:///predictions.db",
    
    # --- Legacy Plugin Names (for plugin loading) ---
    "endpoint_plugins": ["predict_endpoint"],
}
