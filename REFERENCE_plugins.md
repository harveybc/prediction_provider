# Plugin Reference

Complete reference for all plugin types and available plugins in the Prediction Provider system.

## Plugin Architecture

Plugins are loaded via Python entry points defined in `setup.py`. The `plugin_loader.py` module uses `importlib.metadata.entry_points()` to discover and instantiate plugins.

### Common Plugin Interface

Every plugin class must expose:

```python
class MyPlugin:
    # Default parameter values (dict)
    plugin_params = {"param1": "default_value"}
    
    # Keys to include in debug output (list)
    plugin_debug_vars = ["param1"]
    
    def __init__(self, config=None):
        """Initialize with optional config dict."""
        ...
    
    def set_params(self, **kwargs):
        """Update parameters."""
        ...
```

### Plugin Loading

```python
from app.plugin_loader import load_plugin

# Load by entry point group and name
plugin_class, required_params = load_plugin('predictor.plugins', 'default_predictor')
instance = plugin_class(config)
instance.set_params(**config)
```

Entry point groups:
- `core.plugins`
- `feeder.plugins`
- `pipeline.plugins`
- `predictor.plugins`
- `endpoints.plugins`

---

## Core Plugins

### `default_core` — DefaultCorePlugin

**Module**: `plugins_core.default_core`

The central orchestrator. Creates the FastAPI application, registers all routes and middleware, manages plugin lifecycle.

**Parameters**:
| Parameter | Type | Default | Description |
|---|---|---|---|
| `host` | str | `"127.0.0.1"` | Server bind address |
| `port` | int | `8000` | Server port |
| `reload` | bool | `False` | Uvicorn auto-reload |
| `workers` | int | `1` | Uvicorn workers |

**Key Methods**:
- `set_plugins(plugins)` — Receives dict of all loaded plugins, initializes pipeline with predictor+feeder
- `start()` — Starts uvicorn server
- `stop()` — Stops the server (placeholder)

**Note**: The `app` FastAPI instance is created at module level and is importable directly:
```python
from plugins_core.default_core import app
```

---

## Feeder Plugins

### `default_feeder` — DefaultFeeder

**Module**: `plugins_feeder.default_feeder`

Fetches financial data from yfinance or CSV files. Supports normalization, date filtering, and feature selection.

**Parameters**:
| Parameter | Type | Default | Description |
|---|---|---|---|
| `data_source` | str | `"yfinance"` | `"yfinance"` or `"file"` |
| `data_file_path` | str | `None` | Path to CSV when `data_source="file"` |
| `date_column` | str | `"DATE_TIME"` | Name of datetime column |
| `feature_columns` | list | `None` | Columns to select (None = all) |
| `instrument` | str | `"MSFT"` | Ticker symbol for yfinance |
| `correlated_instruments` | list | `[]` | Additional instruments |
| `n_batches` | int | `1` | Number of data batches |
| `batch_size` | int | `256` | Rows per batch |
| `window_size` | int | `256` | Sliding window size |
| `use_normalization_json` | str | `None` | Path to normalization params JSON |
| `target_column` | str | `"CLOSE"` | Target column name |

**Key Methods**:
- `fetch()` → `pd.DataFrame` — Fetch data from configured source
- `fetch_data_for_period(start_date, end_date, additional_previous_ticks)` — Fetch with date range (if supported)

### Other Feeder Plugins (not registered as entry points)

- `real_feeder.py` / `real_feeder_original.py` / `real_feeder_modular.py` — Real-time data fetchers
- `fe_replicator_feeder.py` — Feature engineering replicator
- `data_fetcher.py`, `data_normalizer.py`, `data_validator.py` — Utility feeder modules
- `feature_generator.py`, `stl_feature_generator.py`, `stl_preprocessor.py` — Feature generation
- `technical_indicators.py` — Technical indicator computation

---

## Pipeline Plugins

### `default_pipeline` — DefaultPipelinePlugin

**Module**: `plugins_pipeline.default_pipeline`

Orchestrates feeder → predictor flow. Manages prediction lifecycle and database storage.

**Parameters**:
| Parameter | Type | Default | Description |
|---|---|---|---|
| `pipeline_enabled` | bool | `True` | Enable/disable pipeline |
| `prediction_interval` | int | `300` | Seconds between prediction cycles |
| `db_path` | str | `"prediction_provider.db"` | SQLite database path |
| `enable_logging` | bool | `True` | Enable logging |
| `log_level` | str | `"INFO"` | Log level |

**Key Methods**:
- `initialize(predictor_plugin, feeder_plugin)` — Set up plugins and database
- `run_request(request: dict) → dict` — Run single prediction for API request. Calls `feeder.fetch()` then `predictor.predict_request(df, request)`.
- `run()` — Main loop: fetch → predict → store on interval
- `request_prediction() → int` — Create pending prediction in DB
- `get_system_status() → dict` — System status
- `stop()` — Stop pipeline loop

### `enhanced_pipeline` — EnhancedPipelinePlugin

**Module**: `plugins_pipeline.enhanced_pipeline`

**Not registered as entry point** — must be loaded manually.

Extends default pipeline with date range support and real-time mode.

**Additional Parameters**:
| Parameter | Type | Default | Description |
|---|---|---|---|
| `data_lookback_hours` | int | `720` | Hours to look back |
| `additional_previous_ticks` | int | `50` | Extra ticks for indicators |
| `use_custom_date_range` | bool | `False` | Use custom start/end |
| `custom_start_date` | str | `None` | Custom start date |
| `custom_end_date` | str | `None` | Custom end date |
| `real_time_mode` | bool | `True` | Real-time data fetching |

**Additional Methods**:
- `set_custom_date_range(start_date, end_date)` — Set custom date range
- `enable_real_time_mode(lookback_hours)` — Enable real-time mode
- `run_single_prediction(start_date, end_date)` — One-shot prediction

---

## Predictor Plugins

### `default_predictor` — DefaultPredictor

**Module**: `plugins_predictor.default_predictor`

Loads Keras/sklearn/PyTorch models and makes predictions with optional MC-dropout uncertainty estimation. Also supports an "ideal predictor" mode that returns actual future values from the dataset.

**Parameters**:
| Parameter | Type | Default | Description |
|---|---|---|---|
| `model_path` | str | `None` | Path to trained model file |
| `normalization_params_path` | str | `None` | Path to normalization JSON |
| `model_type` | str | `"keras"` | `"keras"`, `"sklearn"`, `"pytorch"` |
| `prediction_horizon` | int | `6` | Steps ahead to predict |
| `mc_samples` | int | `100` | Monte Carlo dropout samples |
| `batch_size` | int | `32` | Prediction batch size |
| `use_gpu` | bool | `True` | Use GPU if available |
| `gpu_memory_limit` | int | `None` | GPU memory limit (MB) |
| `enable_mixed_precision` | bool | `False` | Mixed precision training |
| `model_cache_size` | int | `5` | Models to keep in cache |
| `prediction_confidence_level` | float | `0.95` | Confidence level |
| `prediction_target_column` | str | `"close_price"` | Target column for de-normalization |

**Key Methods**:

- `load_model(model_path=None)` — Load model from file into cache
- `predict(input_data)` → `np.ndarray` — Basic prediction (also supports `predict(model_name, data)` overload)
- `predict_with_uncertainty(input_data, mc_samples=None)` → `dict` — MC-dropout uncertainty estimation. Returns:
  ```json
  {
    "prediction_timestamp": "ISO string",
    "prediction": [[values]],
    "uncertainty": [[values]],
    "metadata": {"model_path": "...", "mc_samples": 100, "de_normalized": true}
  }
  ```
- `predict_request(input_df, request)` → `dict` — Ideal baseline predictor for API requests. Looks up actual future values in the dataframe. Returns:
  ```json
  {
    "mode": "ideal_future_baseline",
    "date_column": "DATE_TIME",
    "target_column": "CLOSE",
    "baseline_datetime": "ISO string",
    "baseline_value": 100.0,
    "horizons": [1, 2, 3],
    "predictions": [101.0, 102.0, 103.0],
    "future_datetimes": ["ISO", "ISO", "ISO"],
    "uncertainty": [0.0, 0.0, 0.0],
    "errors": []
  }
  ```
- `get_model_info()` → `dict` — Model metadata
- `validate_input_shape(input_data)` → `bool` — Shape validation

### `noisy_ideal_predictor` — NoisyIdealPredictor

**Module**: `plugins_predictor.noisy_ideal_predictor`

Takes ideal (look-ahead) predictions from OHLC CSV data and adds configurable Gaussian noise. Designed for noise-sweep experiments to measure how prediction quality affects strategy performance.

**Parameters**:
| Parameter | Type | Default | Description |
|---|---|---|---|
| `csv_file` | str | `None` | Path to OHLC CSV with DATE_TIME, CLOSE columns |
| `noise_std` | float | `0.0` | Std dev of Gaussian noise (price units) |
| `noise_seed` | int | `42` | Random seed for reproducibility |
| `close_column` | str | `"CLOSE"` | Close price column name |
| `datetime_column` | str | `"DATE_TIME"` | Datetime column name |
| `hourly_horizons` | int | `6` | Number of hourly prediction horizons |
| `daily_horizons` | int | `6` | Number of daily prediction horizons |
| `prediction_horizon` | int | `6` | Compatibility parameter |

**Key Methods**:

- `load_data(csv_file)` — Load OHLC CSV data
- `predict_at(timestamp)` → `dict` — Generate predictions for a specific timestamp:
  ```json
  {
    "hourly_predictions": [100.1, 100.2, ...],
    "daily_predictions": [101.0, 102.0, ...],
    "timestamp": "ISO string",
    "noise_std": 0.5
  }
  ```
- `generate_all_predictions()` → `dict` — Generate prediction DataFrames for all timestamps:
  ```python
  {"hourly": pd.DataFrame, "daily": pd.DataFrame}
  # Columns: Prediction_h_1..Prediction_h_N, Prediction_d_1..Prediction_d_N
  ```
- `predict(input_data)` → `dict` — Pipeline compatibility method. Accepts dict with `timestamp` key or string/Timestamp.

**Usage Example**:
```python
predictor = NoisyIdealPredictor({
    "csv_file": "data/eurusd_hourly.csv",
    "noise_std": 0.5,
    "noise_seed": 42,
    "hourly_horizons": 6,
    "daily_horizons": 6
})

# Single timestamp prediction
result = predictor.predict_at("2024-01-15 10:00:00")

# Generate all predictions for noise sweep
all_preds = predictor.generate_all_predictions()
hourly_df = all_preds["hourly"]  # DataFrame with Prediction_h_1..h_6
```

---

## Endpoint Plugins

### `default_endpoints` — DefaultEndpointsPlugin

**Module**: `plugins_endpoints.default_endpoints`

Provides a FastAPI router for health checks, system info, and predictions.

**Parameters**:
| Parameter | Type | Default | Description |
|---|---|---|---|
| `host` | str | `"0.0.0.0"` | Endpoint host |
| `port` | int | `5000` | Endpoint port |
| `debug` | bool | `False` | Debug mode |
| `db_path` | str | `"prediction_provider.db"` | Database path |

### `predict_endpoint` — PredictEndpointPlugin

**Module**: `plugins_endpoints.predict_endpoint`

### `health_endpoint` — HealthEndpointPlugin

**Module**: `plugins_endpoints.health_endpoint`

### `info_endpoint` — InfoEndpointPlugin

**Module**: `plugins_endpoints.info_endpoint`

### `metrics_endpoint` — MetricsEndpointPlugin

**Module**: `plugins_endpoints.metrics_endpoint`

**Note**: Most endpoint logic is implemented directly in `plugins_core/default_core.py` rather than through these endpoint plugins. These exist primarily for the plugin loading system.

---

## Creating New Plugins

### Step 1: Create the Plugin Class

```python
# plugins_predictor/my_predictor.py
class MyPredictor:
    plugin_params = {
        "my_param": "default_value",
        "prediction_horizon": 6,
    }
    
    plugin_debug_vars = ["my_param"]
    
    def __init__(self, config=None):
        self.params = self.plugin_params.copy()
        if config:
            self.set_params(**config)
    
    def set_params(self, **kwargs):
        for k, v in kwargs.items():
            if k in self.params:
                self.params[k] = v
    
    def predict(self, input_data):
        # Your prediction logic
        return {"prediction": [1.0, 2.0, 3.0]}
    
    def predict_request(self, input_df, request):
        # For pipeline integration
        return {"predictions": [...], "uncertainty": [...]}
```

### Step 2: Register the Entry Point

In `setup.py`, add to the appropriate group:

```python
entry_points={
    'predictor.plugins': [
        'my_predictor=plugins_predictor.my_predictor:MyPredictor',
    ],
}
```

### Step 3: Reinstall

```bash
pip install -e .
```

### Step 4: Use via Configuration

```bash
prediction_provider --predictor_plugin my_predictor --my_param custom_value
```

Or in config JSON:
```json
{"predictor_plugin": "my_predictor", "my_param": "custom_value"}
```
