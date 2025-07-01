# Prediction Provider - Files Reference Documentation

## Table of Contents
1. [System Overview](#1-system-overview)
2. [Core Application Files](#2-core-application-files)
3. [Plugin Architecture](#3-plugin-architecture)
4. [Core Plugins](#4-core-plugins)
5. [Endpoint Plugins](#5-endpoint-plugins)
6. [Processing Plugins](#6-processing-plugins)
7. [Configuration and Examples](#7-configuration-and-examples)
8. [Setup and Dependencies](#8-setup-and-dependencies)

## 1. System Overview

The Prediction Provider is a robust, plugin-based API service designed for machine learning prediction workflows. It implements a modular architecture with strict separation of concerns, supporting dynamic plugin loading, Flask-based REST API, SQLAlchemy database integration, and asynchronous prediction processing.

### Architecture Principles
- **Plugin-based Architecture**: Modular design with 5 plugin types (core, endpoints, feeder, predictor, pipeline)
- **Separation of Concerns**: Each component has a single responsibility
- **Dynamic Loading**: Plugins are loaded at runtime based on configuration
- **Asynchronous Processing**: Predictions run in background threads
- **Database Integration**: SQLAlchemy for persistent storage
- **RESTful API**: Flask-based HTTP endpoints with authentication

## 2. Core Application Files

### 2.1 `/app/main.py`
**Primary Entry Point and Application Orchestrator**

#### Main Functions:
- **`main()`**: Application entry point that orchestrates the entire system startup
- **Dynamic Plugin Loading**: Loads all plugin types from their respective namespaces
- **Configuration Management**: Merges configuration from multiple sources
- **Flask Server Initialization**: Sets up and starts the web server

#### Key Responsibilities:
1. Load plugins from 5 namespaces: core, endpoints, feeder, predictor, pipeline
2. Merge configuration using `config_merger`
3. Initialize database and Flask application
4. Register all endpoint plugins with the Flask app
5. Start the HTTP server

#### Plugin Namespaces:
- `core.plugins` → `plugins_core`
- `endpoints.plugins` → `plugins_endpoints`
- `feeder.plugins` → `plugins_feeder`
- `predictor.plugins` → `plugins_predictor`
- `pipeline.plugins` → `plugins_pipeline`

### 2.2 `/app/models.py`
**Database Models and Session Management**

#### Main Classes:
- **`PendingPredictionRequest`**: SQLAlchemy model for prediction requests

#### Model Fields:
- `id`: Primary key (auto-increment)
- `model_path`: Path to the ML model file
- `target_datetime`: Target prediction datetime
- `batch_size`: Batch size for processing
- `features`: JSON string of feature list
- `status`: Request status (pending/processing/completed/failed)
- `results`: JSON string of prediction results
- `error_message`: Error details if failed
- `created_at`: Request creation timestamp
- `updated_at`: Last update timestamp

#### Helper Functions:
- **`create_database_engine(database_url)`**: Creates SQLAlchemy engine
- **`get_session_maker(engine)`**: Creates session factory
- **`create_database(database_url)`**: Initializes database schema
- **`to_dict()`**: Converts model instance to dictionary

### 2.3 `/app/plugin_loader.py`
**Dynamic Plugin Loading System**

#### Main Functions:
- **`load_plugin(namespace, plugin_name, config=None)`**: Loads a plugin by namespace and name
- **`load_plugins_from_namespace(namespace, config=None)`**: Loads all plugins from a namespace
- **`get_available_plugins(namespace)`**: Lists available plugins in namespace

#### Plugin Loading Process:
1. Discover plugins using setuptools entry points
2. Import plugin modules dynamically
3. Instantiate plugin classes with configuration
4. Return plugin instances for registration

### 2.4 `/app/cli.py`
**Command Line Interface**

#### Main Functions:
- **`create_cli()`**: Creates argument parser for CLI commands
- **`main()`**: CLI entry point with command routing

#### Supported Commands:
- Database initialization
- Configuration validation
- Plugin listing and debugging

### 2.5 `/app/config.py`
**Configuration Management Base**

#### Functions:
- **`load_config(config_path)`**: Loads configuration from JSON file
- **`validate_config(config)`**: Validates configuration structure
- **`get_default_config()`**: Returns default configuration values

### 2.6 `/app/config_handler.py`
**Advanced Configuration Processing**

#### Main Functions:
- **`ConfigHandler`**: Class for advanced config manipulation
- **`merge_configs()`**: Merges multiple configuration sources
- **`validate_plugin_configs()`**: Validates plugin-specific configurations

### 2.7 `/app/config_merger.py`
**Configuration Merging Logic**

#### Main Functions:
- **`merge_config_files(file_paths)`**: Merges multiple config files
- **`deep_merge(dict1, dict2)`**: Performs deep dictionary merge
- **`resolve_config_conflicts()`**: Handles configuration conflicts

## 3. Plugin Architecture

### Plugin Base Requirements
All plugins must implement these methods:

#### Required Methods:
- **`__init__(self, config=None)`**: Plugin initialization
- **`set_params(self, **kwargs)`**: Update plugin parameters
- **`get_debug_info(self)`**: Return debug information
- **`add_debug_info(self, debug_info)`**: Add debug info to dictionary

#### Required Attributes:
- **`plugin_params`**: Dictionary of default parameters
- **`plugin_debug_vars`**: List of variables to include in debug info

## 4. Core Plugins

### 4.1 `/plugins_core/default_core.py`
**Core System Infrastructure Plugin**

#### Class: `DefaultCorePlugin`

#### Main Responsibilities:
- **Flask Application Setup**: Initialize Flask app with proper configuration
- **CORS Configuration**: Enable cross-origin resource sharing
- **Authentication Setup**: JWT and basic authentication support
- **Database Session Management**: Request-scoped database sessions
- **Error Handling**: Global error handlers for API responses

#### Key Methods:
- **`setup_flask_app(app)`**: Configures Flask application
- **`setup_cors(app)`**: Enables CORS with proper headers
- **`setup_auth(app)`**: Configures JWT and basic authentication
- **`setup_database_session(app)`**: Sets up request-scoped DB sessions
- **`setup_error_handlers(app)`**: Global error handling

#### Authentication Features:
- JWT token validation
- Basic HTTP authentication fallback
- Request-scoped user context

## 5. Endpoint Plugins

### 5.1 `/plugins_endpoints/predict_endpoint.py`
**Prediction Request Handling Plugin**

#### Class: `PredictEndpointPlugin`

#### Main Functionality:
- **POST `/predict`**: Create new prediction requests
- **GET `/predict?request_id=X`**: Retrieve prediction status and results
- **Asynchronous Processing**: Background thread execution
- **Database Integration**: Persistent request storage

#### Key Methods:
- **`register(app)`**: Registers endpoints with Flask app
- **`_handle_prediction_request()`**: Processes POST requests
- **`_handle_prediction_status()`**: Handles GET status requests
- **`_process_prediction(request_id)`**: Background prediction processing

#### Request Format (POST):
```json
{
    "model_path": "path/to/model.keras",
    "target_datetime": "2024-01-01T12:00:00Z",
    "batch_size": 32,
    "features": ["feature1", "feature2"]
}
```

#### Response Format:
```json
{
    "request_id": 123,
    "status": "pending|processing|completed|failed",
    "results": {...},
    "error_message": "...",
    "created_at": "...",
    "updated_at": "..."
}
```

#### Asynchronous Processing Flow:
1. Validate request payload
2. Create database record with 'pending' status
3. Start background thread for processing
4. Return request_id immediately
5. Background thread processes prediction
6. Update database with results or error

### 5.2 `/plugins_endpoints/health_endpoint.py`
**System Health Monitoring Plugin**

#### Class: `HealthEndpointPlugin`

#### Endpoint: `GET /health`

#### Health Checks:
- **Database Connectivity**: Tests database connection
- **System Resources**: Memory and CPU usage
- **Plugin Status**: Validates all plugins are loaded
- **Service Dependencies**: External service availability

#### Response Format:
```json
{
    "status": "healthy|degraded|unhealthy",
    "timestamp": "2024-01-01T12:00:00Z",
    "checks": {
        "database": "ok|error",
        "memory": {"usage": 45.2, "limit": 1024},
        "plugins": {"loaded": 5, "total": 5}
    }
}
```

### 5.3 `/plugins_endpoints/metrics_endpoint.py`
**System Metrics and Statistics Plugin**

#### Class: `MetricsEndpointPlugin`

#### Endpoint: `GET /metrics`

#### Metrics Provided:
- **Request Counts**: Total, successful, failed predictions
- **Performance Metrics**: Average processing time, throughput
- **System Metrics**: Memory usage, CPU load
- **Database Metrics**: Connection pool status, query performance

#### Response Format:
```json
{
    "predictions": {
        "total": 1500,
        "successful": 1450,
        "failed": 50,
        "pending": 5
    },
    "performance": {
        "avg_processing_time": 2.5,
        "requests_per_hour": 120
    },
    "system": {
        "memory_usage_mb": 512,
        "cpu_usage_percent": 15.5
    }
}
```

### 5.4 `/plugins_endpoints/info_endpoint.py`
**System Information Plugin**

#### Class: `InfoEndpointPlugin`

#### Endpoint: `GET /info`

#### Information Provided:
- **System Version**: Application version and build info
- **Plugin Information**: Loaded plugins and their versions
- **Configuration Summary**: Non-sensitive config parameters
- **API Documentation**: Available endpoints and their descriptions

#### Response Format:
```json
{
    "version": "1.0.0",
    "build_date": "2024-01-01",
    "plugins": {
        "core": ["default_core"],
        "endpoints": ["predict", "health", "metrics", "info"],
        "predictor": ["default_predictor"],
        "feeder": ["default_feeder"],
        "pipeline": ["default_pipeline"]
    },
    "endpoints": [
        {"path": "/predict", "methods": ["GET", "POST"]},
        {"path": "/health", "methods": ["GET"]},
        {"path": "/metrics", "methods": ["GET"]},
        {"path": "/info", "methods": ["GET"]}
    ]
}
```

## 6. Processing Plugins

### 6.1 `/plugins_feeder/default_feeder.py`
**Data Feeding and Retrieval Plugin**

#### Class: `DefaultFeederPlugin`

#### Main Responsibilities:
- **Data Source Management**: File and API data sources
- **Batch Processing**: Configurable batch sizes
- **Date-based Filtering**: Time-series data retrieval
- **Feature Selection**: Dynamic feature subset selection

#### Key Methods:
- **`fetch_data_for_prediction(target_datetime)`**: Main data retrieval method
- **`fetch_from_file(file_path)`**: File-based data loading
- **`fetch_from_api(api_url)`**: API-based data retrieval
- **`filter_by_datetime(data, target_datetime)`**: Time-based filtering
- **`select_features(data, features)`**: Feature subset selection
- **`create_batches(data, batch_size)`**: Batch data preparation

#### Supported Data Sources:
- **CSV Files**: Pandas-based loading with datetime parsing
- **JSON Files**: Structured data loading
- **REST APIs**: HTTP-based data retrieval
- **Database Queries**: Direct database access

#### Data Processing Pipeline:
1. Load data from source (file/API/database)
2. Parse and validate datetime columns
3. Filter data based on target datetime
4. Select specified features
5. Create batches of specified size
6. Return formatted data with metadata

### 6.2 `/plugins_predictor/default_predictor.py`
**Machine Learning Prediction Plugin**

#### Class: `DefaultPredictorPlugin`

#### Main Responsibilities:
- **Model Loading**: Keras/TensorFlow model loading
- **Prediction Generation**: Forward pass inference
- **Uncertainty Estimation**: Monte Carlo dropout or ensemble methods
- **Result Formatting**: Structured prediction output

#### Key Methods:
- **`load_model(model_path)`**: Loads ML model from file
- **`predict(data)`**: Generates predictions
- **`predict_with_uncertainty(data)`**: Predictions with uncertainty estimates
- **`estimate_uncertainty(data, num_samples=100)`**: Monte Carlo uncertainty
- **`preprocess_data(data)`**: Data preprocessing for model input
- **`postprocess_predictions(predictions)`**: Prediction post-processing

#### Supported Model Types:
- **Keras Models**: .keras and .h5 files
- **TensorFlow SavedModel**: Directory-based models
- **ONNX Models**: Cross-platform model format
- **Scikit-learn Models**: Pickle-based models

#### Uncertainty Estimation Methods:
- **Monte Carlo Dropout**: Multiple forward passes with dropout
- **Ensemble Methods**: Multiple model predictions
- **Bayesian Neural Networks**: Variational inference
- **Bootstrap Sampling**: Statistical uncertainty estimation

#### Prediction Pipeline:
1. Load and validate model
2. Preprocess input data
3. Generate predictions
4. Estimate uncertainties
5. Post-process results
6. Format output with metadata

### 6.3 `/plugins_pipeline/default_pipeline.py`
**System Orchestration and Pipeline Plugin**

#### Class: `DefaultPipelinePlugin`

#### Main Responsibilities:
- **Plugin Coordination**: Orchestrates feeder and predictor plugins
- **Caching Management**: Result caching and invalidation
- **Error Handling**: Pipeline-level error management
- **Performance Monitoring**: Pipeline execution metrics

#### Key Methods:
- **`execute_prediction_pipeline(request_data)`**: Main pipeline execution
- **`coordinate_plugins(feeder, predictor)`**: Plugin coordination
- **`manage_cache(cache_key, result)`**: Caching operations
- **`handle_pipeline_errors(error, context)`**: Error handling
- **`monitor_performance(start_time, end_time)`**: Performance tracking

#### Pipeline Execution Flow:
1. Validate input parameters
2. Check cache for existing results
3. Coordinate feeder plugin for data retrieval
4. Coordinate predictor plugin for inference
5. Cache results if successful
6. Return formatted results with metadata
7. Log performance metrics

#### Caching Strategy:
- **Cache Keys**: Based on model path, datetime, and features
- **Cache Invalidation**: Time-based and manual invalidation
- **Cache Storage**: In-memory and persistent storage options
- **Cache Metrics**: Hit rate and performance tracking

## 7. Configuration and Examples

### 7.1 `/examples/config/default_config.json`
**Default System Configuration**

#### Configuration Sections:
- **Server Settings**: Port, host, debug mode
- **Database Configuration**: Connection string, pool settings
- **Plugin Configuration**: Plugin-specific parameters
- **Authentication Settings**: JWT secrets, token expiration
- **Logging Configuration**: Log levels, file paths

#### Sample Configuration:
```json
{
    "server": {
        "host": "0.0.0.0",
        "port": 5000,
        "debug": false
    },
    "database": {
        "url": "sqlite:///prediction_provider.db",
        "pool_size": 10
    },
    "plugins": {
        "core_plugin": "default_core",
        "predictor_plugin": "default_predictor",
        "feeder_plugin": "default_feeder",
        "pipeline_plugin": "default_pipeline"
    },
    "auth": {
        "jwt_secret": "your-secret-key",
        "token_expiration": 3600
    }
}
```

### 7.2 `/examples/scripts/create_database.py`
**Database Initialization Script**

#### Main Functions:
- **`create_database()`**: Initializes database schema
- **`validate_database()`**: Validates database structure
- **`populate_test_data()`**: Adds sample data for testing

#### Usage:
```bash
cd /path/to/prediction_provider
python examples/scripts/create_database.py
```

#### Database Setup Process:
1. Create database engine
2. Create all tables from models
3. Validate table structure
4. Optionally populate test data
5. Verify database connectivity

## 8. Setup and Dependencies

### 8.1 `/setup.py`
**Package Installation and Plugin Registration**

#### Entry Points Configuration:
```python
entry_points={
    'core.plugins': [
        'default_core = plugins_core.default_core:DefaultCorePlugin',
    ],
    'endpoints.plugins': [
        'predict_endpoint = plugins_endpoints.predict_endpoint:PredictEndpointPlugin',
        'health_endpoint = plugins_endpoints.health_endpoint:HealthEndpointPlugin',
        'metrics_endpoint = plugins_endpoints.metrics_endpoint:MetricsEndpointPlugin',
        'info_endpoint = plugins_endpoints.info_endpoint:InfoEndpointPlugin',
    ],
    'feeder.plugins': [
        'default_feeder = plugins_feeder.default_feeder:DefaultFeederPlugin',
    ],
    'predictor.plugins': [
        'default_predictor = plugins_predictor.default_predictor:DefaultPredictorPlugin',
    ],
    'pipeline.plugins': [
        'default_pipeline = plugins_pipeline.default_pipeline:DefaultPipelinePlugin',
    ],
}
```

#### Dependencies:
- **Flask**: Web framework and API server
- **SQLAlchemy**: Database ORM and connection management
- **TensorFlow**: Machine learning model support
- **Pandas**: Data manipulation and analysis
- **NumPy**: Numerical computing
- **Requests**: HTTP client for API calls
- **PyJWT**: JSON Web Token authentication
- **Flask-CORS**: Cross-origin resource sharing
- **psutil**: System resource monitoring

### 8.2 `/requirements.txt`
**Python Package Dependencies**

#### Core Dependencies:
```
flask>=2.3.0
flask-cors>=4.0.0
sqlalchemy>=2.0.0
tensorflow>=2.13.0
pandas>=2.0.0
numpy>=1.24.0
requests>=2.31.0
pyjwt>=2.8.0
psutil>=5.9.0
```

#### Development Dependencies:
```
pytest>=7.4.0
pytest-cov>=4.1.0
black>=23.7.0
flake8>=6.0.0
mypy>=1.5.0
```

## Usage Examples

### Starting the Server
```bash
cd /path/to/prediction_provider
python -m app.main
```

### Making a Prediction Request
```bash
curl -X POST http://localhost:5000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "model_path": "path/to/model.keras",
    "target_datetime": "2024-01-01T12:00:00Z",
    "batch_size": 32,
    "features": ["feature1", "feature2"]
  }'
```

### Checking Prediction Status
```bash
curl "http://localhost:5000/predict?request_id=123"
```

### System Health Check
```bash
curl http://localhost:5000/health
```

## Plugin Development Guide

### Creating a New Plugin

1. **Choose Plugin Type**: core, endpoints, feeder, predictor, or pipeline
2. **Implement Required Methods**: `__init__`, `set_params`, `get_debug_info`, `add_debug_info`
3. **Define Plugin Attributes**: `plugin_params`, `plugin_debug_vars`
4. **Add Entry Point**: Update `setup.py` with plugin registration
5. **Test Plugin**: Use plugin_loader to test loading and functionality

### Plugin Template
```python
class MyCustomPlugin:
    plugin_params = {
        "param1": "default_value",
        "param2": 42
    }
    
    plugin_debug_vars = ["param1", "param2"]
    
    def __init__(self, config=None):
        self.params = self.plugin_params.copy()
        self.config = config or {}
        if config:
            self.set_params(**config)
    
    def set_params(self, **kwargs):
        for key, value in kwargs.items():
            self.params[key] = value
    
    def get_debug_info(self):
        return {var: self.params.get(var) for var in self.plugin_debug_vars}
    
    def add_debug_info(self, debug_info):
        debug_info.update(self.get_debug_info())
    
    # Plugin-specific methods here
```

This reference document provides comprehensive coverage of all files, their functionalities, and the overall system architecture of the Prediction Provider.

#### Main Functions:
- **`load_plugin(group, name)`**: Loads a specific plugin by group and name from entry points
- **Entry Point Groups**:
  - `pipeline.plugins`: Pipeline orchestration plugins
  - `feeder.plugins`: Data feeding plugins  
  - `predictor.plugins`: Model prediction plugins
  - `endpoints.plugins`: API endpoint plugins
  - `core.plugins`: Core Flask configuration plugins

### 2.3 `app/cli.py`
**Purpose**: Command-line interface argument parsing.

#### Main Functions:
- **`parse_args()`**: Parses command-line arguments including config files, server settings, and plugin selections
- **Supported Arguments**:
  - `--load-config`: Load local configuration file
  - `--remote-load-config`: Load remote configuration
  - `--server-port`: Flask server port
  - `--server-host`: Flask server host
  - `--debug`: Enable debug mode
  - Plugin selection arguments

### 2.4 `app/config.py`
**Purpose**: Default configuration values and settings.

#### Main Components:
- **`DEFAULT_VALUES`**: Dictionary containing all default configuration parameters
- **Default Settings**: Server port, host, debug mode, database URL, authentication settings
- **Plugin Defaults**: Default plugin names and parameters

### 2.5 `app/config_handler.py`
**Purpose**: Configuration loading and saving operations.

#### Main Functions:
- **`load_config(filepath)`**: Load configuration from local JSON file
- **`save_config(config, filepath)`**: Save configuration to local JSON file
- **`remote_load_config(url, username, password)`**: Load configuration from remote URL
- **`remote_save_config(config, url, username, password)`**: Save configuration to remote endpoint
- **`remote_log(message, url, username, password)`**: Send log messages to remote endpoint

### 2.6 `app/config_merger.py`
**Purpose**: Configuration merging and processing.

#### Main Functions:
- **`merge_config(...)`**: Merge configurations from multiple sources (defaults, files, CLI, plugins)
- **`process_unknown_args(unknown_args)`**: Process unknown command-line arguments into configuration dictionary
- **Priority Order**: CLI args > File config > Plugin params > Defaults

---

## 3. Plugin System

### 3.1 Plugin Base Structure
All plugins must implement the following mandatory methods and attributes:

#### Required Attributes:
- **`plugin_params`**: Dictionary with default parameter values
- **`plugin_debug_vars`**: List of important debug variable names

#### Required Methods:
- **`__init__(self, config=None)`**: Initialize plugin with optional configuration
- **`set_params(self, **kwargs)`**: Update plugin parameters
- **`get_debug_info(self)`**: Return debug information dictionary
- **`add_debug_info(self, debug_info)`**: Add debug info to provided dictionary

### 3.2 Core Plugins (`plugins_core/`)

#### 3.2.1 `plugins_core/default_core.py` - `DefaultCorePlugin`
**Purpose**: Flask application initialization and core middleware setup.

##### Main Functions:
- **`init_app(self, config)`**: Initialize Flask application with core configuration
- **`_setup_authentication(self)`**: Configure JWT or Basic authentication middleware
- **`_setup_database(self)`**: Set up database session handling for requests
- **`_setup_error_handlers(self)`**: Configure global error handlers
- **`generate_jwt_token(self, user_id, username)`**: Generate JWT tokens for authentication

##### Key Features:
- CORS configuration for cross-origin requests
- JWT and Basic authentication support
- Per-request database session management
- Global error handling (404, 405, 500)
- Security middleware configuration

### 3.3 Endpoint Plugins (`plugins_endpoints/`)

#### 3.3.1 `plugins_endpoints/predict_endpoint.py` - `PredictEndpointPlugin`
**Purpose**: Handle prediction requests via POST and GET methods with database storage.

##### Main Functions:
- **`register(self, app)`**: Register prediction endpoints with Flask app
- **`_handle_prediction_request(self)`**: Handle POST requests to create prediction requests
- **`_handle_prediction_status(self)`**: Handle GET requests to retrieve prediction results
- **`_process_prediction(self, request_id)`**: Background thread function for processing predictions

##### API Endpoints:
- **POST `/predict`**: Create new prediction request
  - Required: `model_path`, `target_datetime`
  - Optional: `batch_size`, `features`
  - Returns: `request_id` and status
- **GET `/predict?request_id=<id>`**: Retrieve prediction results
  - Returns: Complete request data including results if completed

##### Key Features:
- Asynchronous prediction processing
- Database persistence of requests and results
- Background thread management
- Model loading and data fetching orchestration
- Uncertainty estimation integration

#### 3.3.2 `plugins_endpoints/health_endpoint.py` - `HealthEndpointPlugin`
**Purpose**: Provide health check endpoints for monitoring.

##### Main Functions:
- **`register(self, app)`**: Register health check endpoints
- **`_get_detailed_health_info(self)`**: Gather detailed system health information
- **`_check_database_health(self)`**: Test database connectivity
- **`_check_components_health(self)`**: Verify component availability

##### API Endpoints:
- **GET `/health`**: Basic health check with optional detailed info
- **GET `/health/ready`**: Readiness check for service availability
- **GET `/health/live`**: Liveness check for service status

#### 3.3.3 `plugins_endpoints/metrics_endpoint.py` - `MetricsEndpointPlugin`
**Purpose**: Provide system metrics and statistics.

##### Main Functions:
- **`register(self, app)`**: Register metrics endpoints
- **`_get_system_metrics(self)`**: Collect system resource metrics using psutil
- **`_get_application_metrics(self)`**: Gather application-specific metrics
- **`_get_prediction_stats(self)`**: Query database for prediction statistics

##### API Endpoints:
- **GET `/metrics`**: Complete metrics including system, application, and prediction stats

##### Metrics Provided:
- CPU and memory usage
- Disk usage and network statistics
- Application uptime and performance
- Prediction request statistics by status

#### 3.3.4 `plugins_endpoints/info_endpoint.py` - `InfoEndpointPlugin`
**Purpose**: Provide application information and API documentation.

##### Main Functions:
- **`register(self, app)`**: Register information endpoints
- **`_get_system_info(self)`**: Collect system information
- **`_get_api_info(self)`**: Generate API documentation

##### API Endpoints:
- **GET `/info`**: Application information with system details
- **GET `/info/version`**: Version and build information
- **GET `/info/api`**: API documentation and endpoint descriptions

### 3.4 Feeder Plugins (`plugins_feeder/`)

#### 3.4.1 `plugins_feeder/default_feeder.py` - `DefaultFeederPlugin`
**Purpose**: Handle data fetching and feeding for predictions.

##### Main Functions:
- **`fetch_data_for_prediction(self, target_datetime, model_input_shape=None)`**: Fetch data required for prediction
- **`_fetch_raw_data(self, start_datetime, end_datetime)`**: Fetch raw data from configured source
- **`_fetch_from_file(self, start_datetime, end_datetime)`**: Read data from CSV/JSON/Parquet files
- **`_fetch_from_api(self, start_datetime, end_datetime)`**: Fetch data from API endpoints
- **`_process_data(self, raw_data, target_datetime)`**: Process and clean raw data
- **`_create_prediction_windows(self, processed_data)`**: Create windowed data for model input

##### Supported Data Sources:
- File-based: CSV, JSON, Parquet formats
- API-based: REST endpoints with authentication
- Database: SQLAlchemy integration (placeholder)

##### Key Features:
- Automatic data windowing based on model requirements
- Missing data handling (forward fill, interpolation, drop)
- Data normalization support
- Feature selection and filtering
- Date range calculation with buffer periods

### 3.5 Predictor Plugins (`plugins_predictor/`)

#### 3.5.1 `plugins_predictor/default_predictor.py` - `DefaultPredictorPlugin`
**Purpose**: Handle model loading, prediction, and evaluation.

##### Main Functions:
- **`load_model(self, model_path=None)`**: Load trained model from file with caching
- **`predict(self, input_data)`**: Make standard predictions using loaded model
- **`predict_with_uncertainty(self, input_data, mc_samples=None)`**: Make predictions with uncertainty estimation
- **`_configure_tensorflow(self)`**: Configure TensorFlow settings (GPU, mixed precision)
- **`validate_input_shape(self, input_data)`**: Validate input data shape compatibility

##### Supported Model Types:
- Keras/TensorFlow models (.keras, .h5)
- Scikit-learn models (via joblib)
- PyTorch models (placeholder)

##### Key Features:
- Model caching for performance
- Monte Carlo dropout for uncertainty estimation
- GPU configuration and memory management
- Mixed precision support
- Input shape validation
- Model metadata loading

### 3.6 Pipeline Plugins (`plugins_pipeline/`)

#### 3.6.1 `plugins_pipeline/default_pipeline.py` - `DefaultPipelinePlugin`
**Purpose**: Orchestrate prediction system components and manage infrastructure.

##### Main Functions:
- **`initialize_prediction_system(self, config, predictor_plugin, feeder_plugin)`**: Initialize system with plugins
- **`process_prediction_request(self, request_data)`**: Process complete prediction request
- **`_validate_system(self)`**: Validate system readiness and component availability
- **`_check_prediction_cache(self, request_data)`**: Check for cached predictions
- **`_cache_prediction(self, request_data, results)`**: Cache prediction results

##### Key Features:
- Component coordination and orchestration
- Prediction caching with expiration
- Active prediction tracking
- System validation and health checks
- Performance monitoring and cleanup

---

## 4. Database Models

### 4.1 `app/models.py`
**Purpose**: SQLAlchemy database models and database utilities.

#### Main Components:

##### 4.1.1 `PendingPredictionRequest` Model
**Purpose**: Store prediction requests and their results.

**Fields**:
- `id`: Primary key (auto-increment)
- `model_path`: Path to the model file
- `target_datetime`: Target datetime for prediction
- `batch_size`: Number of data batches
- `features`: JSON string of required features
- `status`: Request status (pending, processing, completed, failed)
- `results`: JSON string of prediction results
- `error_message`: Error message if failed
- `created_at`: Request creation timestamp
- `updated_at`: Last update timestamp

**Methods**:
- **`to_dict(self)`**: Convert model to dictionary for JSON serialization

##### 4.1.2 Database Utility Functions
- **`create_database_engine(database_url)`**: Create SQLAlchemy engine
- **`create_tables(engine)`**: Create all database tables
- **`get_session_maker(engine)`**: Create session maker
- **`get_db_session()`**: Get database session for current thread
- **`create_database()`**: Initialize complete database with tables

---

## 5. Configuration System

### 5.1 Configuration Sources (Priority Order)
1. **Command-line arguments** (highest priority)
2. **Configuration files** (local and remote)
3. **Plugin-specific parameters**
4. **Default values** (lowest priority)

### 5.2 Configuration Categories

#### 5.2.1 Server Configuration
- `server_host`: Flask server host (default: "0.0.0.0")
- `server_port`: Flask server port (default: 5000)
- `debug`: Debug mode flag (default: false)

#### 5.2.2 Database Configuration
- `database_url`: SQLAlchemy database URL (default: "sqlite:///prediction_provider.db")

#### 5.2.3 Authentication Configuration
- `auth_type`: Authentication type ("none", "basic", "jwt")
- `jwt_secret`: JWT secret key
- `jwt_expiration_hours`: JWT token expiration time
- `cors_enabled`: Enable CORS support
- `allowed_origins`: CORS allowed origins

#### 5.2.4 Plugin Selection
- `pipeline_plugin`: Pipeline plugin name
- `feeder_plugin`: Feeder plugin name
- `predictor_plugin`: Predictor plugin name
- `core_plugin`: Core plugin name
- `endpoint_plugins`: List of endpoint plugin names

#### 5.2.5 Data Configuration
- `data_source`: Data source type ("file", "api", "database")
- `data_file_path`: Path to data file
- `batch_size`: Data batch size
- `window_size`: Sliding window size
- `feature_columns`: List of feature column names
- `target_column`: Target column name
- `date_column`: Date/time column name

#### 5.2.6 Model Configuration
- `model_type`: Model type ("keras", "sklearn", "pytorch")
- `prediction_horizon`: Prediction time horizon
- `mc_samples`: Monte Carlo samples for uncertainty
- `use_gpu`: Enable GPU usage
- `enable_mixed_precision`: Enable mixed precision

---

## 6. Examples and Scripts

### 6.1 `examples/scripts/create_database.py`
**Purpose**: Initialize SQLite database with required tables.

#### Main Functions:
- **`create_prediction_provider_database(db_path)`**: Create database with all tables
- **`main()`**: Command-line interface for database creation

#### Usage:
```bash
python examples/scripts/create_database.py [--db-path path/to/database.db]
```

### 6.2 `examples/config/default_config.json`
**Purpose**: Example configuration file with common settings.

#### Configuration Sections:
- Server settings (host, port, debug)
- Database configuration
- Authentication settings
- Plugin selections
- Data source configuration
- Model parameters
- Pipeline settings

---

## 7. Plugin Architecture Details

### 7.1 Plugin Loading Mechanism

#### Entry Points System
The system uses Python entry points defined in `setup.py` for dynamic plugin discovery:

```python
entry_points={
    'pipeline.plugins': [
        'default_pipeline=plugins_pipeline.default_pipeline:DefaultPipelinePlugin'
    ],
    'feeder.plugins': [
        'default_feeder=plugins_feeder.default_feeder:DefaultFeederPlugin'
    ],
    # ... other plugin groups
}
```

#### Plugin Groups:
1. **`pipeline.plugins`**: System orchestration and coordination
2. **`feeder.plugins`**: Data fetching and preprocessing
3. **`predictor.plugins`**: Model loading and prediction
4. **`endpoints.plugins`**: API endpoint definitions
5. **`core.plugins`**: Flask application core setup

### 7.2 Plugin Interface Contract

#### Mandatory Structure:
Every plugin must implement:

```python
class PluginName:
    # Required class attributes
    plugin_params = {...}  # Default parameters
    plugin_debug_vars = [...]  # Debug variables
    
    # Required methods
    def __init__(self, config=None):
        # Initialize with optional config
    
    def set_params(self, **kwargs):
        # Update parameters
    
    def get_debug_info(self):
        # Return debug information
    
    def add_debug_info(self, debug_info):
        # Add debug info to dictionary
```

#### Plugin-Specific Requirements:

**Endpoint Plugins** must additionally implement:
- `register(self, app)`: Register endpoints with Flask app

**Core Plugins** must additionally implement:
- `init_app(self, config)`: Initialize Flask application

**Feeder Plugins** must additionally implement:
- `fetch_data_for_prediction(self, target_datetime)`: Fetch prediction data

**Predictor Plugins** must additionally implement:
- `load_model(self, model_path)`: Load model from file
- `predict(self, input_data)`: Make predictions
- `predict_with_uncertainty(self, input_data)`: Predictions with uncertainty

### 7.3 Configuration Merging Process

1. **Load Defaults**: Start with `DEFAULT_VALUES` from `app/config.py`
2. **Load File Config**: Merge configuration from files (local/remote)
3. **Process CLI Args**: Override with command-line arguments
4. **Plugin Parameters**: Merge plugin-specific defaults
5. **Final Merge**: Create final configuration dictionary

### 7.4 Request Processing Flow

1. **POST `/predict`**: Create prediction request in database
2. **Background Thread**: Start asynchronous processing
3. **Plugin Loading**: Load predictor and feeder plugins
4. **Model Loading**: Load specified model file
5. **Data Fetching**: Fetch required data using feeder plugin
6. **Prediction**: Generate predictions with uncertainty
7. **Result Storage**: Store results in database
8. **Status Updates**: Update request status throughout process

---

## 8. API Reference

### 8.1 Prediction Endpoints

#### POST `/predict`
Create a new prediction request.

**Request Body**:
```json
{
    "model_path": "path/to/model.keras",
    "target_datetime": "2024-01-01T12:00:00Z",
    "batch_size": 32,
    "features": ["OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"]
}
```

**Response**:
```json
{
    "request_id": 123,
    "status": "pending",
    "message": "Prediction request created successfully"
}
```

#### GET `/predict?request_id=<id>`
Retrieve prediction request status and results.

**Response**:
```json
{
    "id": 123,
    "model_path": "path/to/model.keras",
    "target_datetime": "2024-01-01T12:00:00Z",
    "status": "completed",
    "results": {
        "predictions": [[1.23, 1.24, 1.25]],
        "uncertainties": [[0.01, 0.02, 0.01]],
        "prediction_timestamp": "2024-01-01T12:05:00Z"
    }
}
```

### 8.2 Monitoring Endpoints

#### GET `/health`
Basic health check.

#### GET `/health/ready`
Service readiness check.

#### GET `/health/live`
Service liveness check.

#### GET `/metrics`
System and application metrics.

#### GET `/info`
Application information and API documentation.

---

This reference document provides comprehensive coverage of all files, their purposes, main functions, and the overall architecture of the Prediction Provider system. Each section is structured to help developers understand both the high-level architecture and implementation details.
