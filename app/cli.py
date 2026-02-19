import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Prediction Provider: A plugin-based system for financial time series predictions.")
    
    # Core Service Configuration
    parser.add_argument('--host', type=str, help='Server host address')
    parser.add_argument('--port', type=int, help='Server port number')
    parser.add_argument('--core_plugin', type=str, help='Core plugin to use')
    parser.add_argument('--reload', action='store_true', help='Auto-reload on code changes')
    parser.add_argument('--workers', type=int, help='Number of worker processes')
    
    # Database Configuration  
    parser.add_argument('--database_url', type=str, help='Database connection string')
    parser.add_argument('--database_echo', action='store_true', help='Enable SQL logging')
    parser.add_argument('--database_pool_size', type=int, help='Database connection pool size')
    parser.add_argument('--database_max_overflow', type=int, help='Maximum overflow connections')
    
    # Security Configuration
    parser.add_argument('--secret_key', type=str, help='JWT secret key')
    parser.add_argument('--algorithm', type=str, help='JWT algorithm')
    parser.add_argument('--access_token_expire_minutes', type=int, help='Access token expiration in minutes')
    parser.add_argument('--api_key_expire_days', type=int, help='API key expiration in days')
    parser.add_argument('--require_activation', action='store_true', help='Require user activation')
    
    # Plugin Configuration
    parser.add_argument('--feeder_plugin', type=str, help='Data feeder plugin')
    parser.add_argument('--predictor_plugin', type=str, help='Prediction model plugin')
    parser.add_argument('--pipeline_plugin', type=str, help='Processing pipeline plugin')
    parser.add_argument('--endpoints_plugin', type=str, help='API endpoints plugin')
    
    # Endpoints Plugin Configuration
    parser.add_argument('--endpoints_host', type=str, help='Endpoints host address')
    parser.add_argument('--endpoints_port', type=int, help='Endpoints port number')
    parser.add_argument('--endpoints_debug', action='store_true', help='Enable endpoints debug mode')
    parser.add_argument('--endpoints_db_path', type=str, help='Endpoints database path')
    
    # Prediction Parameters
    parser.add_argument('--instrument', type=str, help='Financial instrument symbol')
    parser.add_argument('--correlated_instruments', type=str, nargs='*', help='List of correlated instruments')
    parser.add_argument('--target_column', type=str, help='Target column for prediction')
    parser.add_argument('--prediction_horizon', type=int, help='Number of periods to predict')
    parser.add_argument('--prediction_timeout', type=int, help='Prediction timeout in seconds')
    parser.add_argument('--max_concurrent_predictions', type=int, help='Maximum concurrent predictions')
    parser.add_argument('--prediction_history_days', type=int, help='Days to keep prediction history')
    parser.add_argument('--prediction_interval', type=int, help='Prediction interval in seconds')
    parser.add_argument('--prediction_confidence_level', type=float, help='Confidence level for predictions')
    parser.add_argument('--prediction_target_column', type=str, help='Target column for prediction output')
    
    # Model Configuration
    parser.add_argument('--model_path', type=str, help='Path to trained model file')
    parser.add_argument('--normalization_params_path', type=str, help='Path to normalization parameters file')
    parser.add_argument('--model_type', type=str, help='Type of model')
    parser.add_argument('--model_cache_size', type=int, help='Number of models to cache')
    
    # Processing Configuration
    parser.add_argument('--n_batches', type=int, help='Number of processing batches')
    parser.add_argument('--batch_size', type=int, help='Size of each batch')
    parser.add_argument('--window_size', type=int, help='Size of sliding window')
    parser.add_argument('--mc_samples', type=int, help='Monte Carlo samples for uncertainty estimation')
    parser.add_argument('--use_normalization_json', type=str, help='Path to normalization JSON file')
    
    # Performance Options
    parser.add_argument('--use_gpu', action='store_true', help='Enable GPU acceleration')
    parser.add_argument('--gpu_memory_limit', type=int, help='GPU memory limit in MB')
    parser.add_argument('--enable_mixed_precision', action='store_true', help='Use mixed precision training')
    
    # Pipeline Configuration
    parser.add_argument('--pipeline_enabled', action='store_true', help='Enable pipeline processing')
    parser.add_argument('--pipeline_db_path', type=str, help='Pipeline database path')
    
    # Logging & Monitoring
    parser.add_argument('--enable_logging', action='store_true', help='Enable system logging')
    parser.add_argument('--log_level', type=str, help='Logging level (DEBUG, INFO, WARNING, ERROR)')
    parser.add_argument('--quiet_mode', action='store_true', help='Suppress output (sets log level to ERROR)')
    
    # User Management
    parser.add_argument('--create_user', type=str, help='Create new user with username')
    parser.add_argument('--username', type=str, help='Username for user operations')
    parser.add_argument('--email', type=str, help='Email for user creation')
    parser.add_argument('--role', type=str, help='User role (client, admin, operator)')
    parser.add_argument('--activate_user', type=str, help='Activate user by username')
    parser.add_argument('--change_password', action='store_true', help='Change user password')
    parser.add_argument('--old_password', type=str, help='Old password for password change')
    parser.add_argument('--new_password', type=str, help='New password for password change')
    
    # File I/O
    parser.add_argument('--load_config', type=str, help='Load configuration from JSON file')
    parser.add_argument('--save_config', type=str, help='Save current configuration to file')
    parser.add_argument('--output_file', type=str, help='Path for prediction output CSV')
    parser.add_argument('--results_file', type=str, help='Path for training/validation statistics CSV')
    
    # Authentication Parameters
    parser.add_argument('--password', type=str, help='Password for API authentication')
    parser.add_argument('--remote_load_config', type=str, help='URL to download remote JSON configuration')
    parser.add_argument('--remote_save_config', type=str, help='URL to save configuration remotely')
    parser.add_argument('--remote_log', type=str, help='URL for remote logging endpoint')
    parser.add_argument('--save_log', type=str, help='Path to save log files')
    
    return parser.parse_known_args()
