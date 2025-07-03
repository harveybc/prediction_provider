# Prediction Provider - Plugin Reference

This document provides a detailed, structured description of the required plugin types in the `prediction_provider` system. It specifies the exact functionality, key methods, and configuration parameters for each plugin type. All plugin classes must be initialized with a mandatory `config` parameter (type `dict`), which is sourced from the central `app/config.py` module and can be overridden by CLI arguments, local JSON files, or remote configurations.

---

## 1. `data_feeder` Plugins

### 1.1. Objective
The primary role of a `data_feeder` plugin is to fetch, construct, and prepare the complete feature set required by the `predictor` or `pipeline` plugins. It is responsible for sourcing all necessary data for the last `n_batches * batch_size` time steps and ensuring it is correctly formatted and normalized.

### 1.2. Key Methods
- `__init__(self, config: dict)`: Initializes the plugin with the global application configuration.
- `fetch(self) -> pd.DataFrame`: Fetches, processes, and returns an updated DataFrame with all required features.

### 1.3. `DefaultFeederPlugin` - Step-by-Step Logic

The `default_feeder` is responsible for the entire data preparation pipeline. Here is a granular breakdown of its responsibilities:

1.  **Data Sourcing**:
    *   **Primary Instrument (e.g., EUR/USD)**: Fetch hourly OHLC (Open, High, Low, Close) data.
    *   **Correlated Instruments (e.g., S&P 500, VIX)**: Fetch daily or hourly data. If daily, the last known value must be forward-filled for each hour of the current day.
    *   **High-Frequency Data**: For each hourly timestamp, fetch the close prices for the last 8 ticks from both 15-minute and 30-minute timeframes.

2.  **Feature Calculation**:
    *   **Technical Indicators**: Calculate all standard indicators (RSI, MACD, ADX, etc.) using the hourly OHLC data.
    *   **Bar-Based Features**: Compute features like `BC-BO` (previous bar's close - open) and `BH-BL` (previous bar's high - low).
    *   **Time-Based Features**: Extract `day_of_month`, `hour_of_day`, and `day_of_week` from the primary `DATE_TIME` column.

3.  **DataFrame Assembly**:
    *   Combine all sourced and calculated features into a single pandas DataFrame.
    *   Ensure the DataFrame contains the **exact 45 columns** specified in `REFERENCE.md` and that they are in the correct order.

4.  **Normalization**:
    *   Load the `min` and `max` normalization values from the JSON file specified by the `use_normalization_json` config parameter.
    *   Apply min-max scaling to **all 44 feature columns** (everything except `DATE_TIME`) to normalize them to a `[0, 1]` range.

### 1.4. Relevant `config` Parameters
- `feeder_plugin`: The name of the feeder plugin to use (e.g., `'default_feeder'`).
- `instrument`: The financial instrument to target (e.g., `'EUR/USD'`).
- `n_batches`: Number of batches to retrieve.
- `batch_size`: Number of records per batch.
- `use_normalization_json`: **Crucial path** to the JSON file containing min/max values for normalization.

---

## 2. `predictor` Plugins

### 2.1. Objective
`predictor` plugins are responsible for loading pre-trained models and generating predictions. They are designed to be agnostic to the model format (e.g., Keras, ONNX, etc.).

### 2.2. Key Methods
- `__init__(self, config: dict)`: Initializes the plugin with the global configuration.
- `load_model(self)`: Loads the model from the path specified in the configuration.
- `predict(self, data: np.ndarray) -> np.ndarray`: Performs inference on the input data and returns the prediction.

### 2.3. Expected Input Data Format
The `default_predictor` expects a NumPy array with the following characteristics:
-   **Shape**: The input array's shape must be `(1, 256, 44)`, where:
    -   `1` is the batch size for a single prediction.
    -   `256` is the `window_size`.
    -   `44` is the number of feature columns (all columns from the feeder except `DATE_TIME`).
-   **Normalization**: All values **must** be normalized to a `[0, 1]` range according to the same `use_normalization_json` file used by the feeder.

### 2.4. Relevant `config` Parameters
- `predictor_plugin`: The name of the predictor plugin to use (e.g., `'default_predictor'`).
- `model_path`: The local file path to the trained model (e.g., `'./predictor_model.keras'`).
- `window_size`: The number of time steps the model requires for one prediction (e.g., `256`).
- `mc_samples`: The number of Monte Carlo samples for uncertainty estimation.

---

## 3. `pipeline` Plugins

### 3.1. Objective
Orchestrate the processing flow from data reception to prediction delivery, allowing for pre- and post-processing transformations.

### 3.2. Key Methods
- `__init__(self, config: dict)`: Initializes the plugin.
- `run(self, data: pd.DataFrame) -> pd.DataFrame`: Executes the defined pipeline sequence.

### 3.3. Relevant `config` Parameters
- `pipeline_plugin`: The name of the pipeline plugin to use (e.g., `'default_pipeline'`).

---

## 4. `endpoint` Plugins

### 4.1. Objective
Define individual RESTful API endpoints using Flask to expose the provider's functionality.

### 4.2. Key Methods
- `__init__(self, config: dict)`: Initializes the plugin.
- `register(self, app: Flask)`: Registers the endpoint with the Flask application instance.

### 4.3. Relevant `config` Parameters
- `endpoint_plugins`: A list of endpoint plugins to load (e.g., `['predict_endpoint']`).

---

## 5. `core` Plugins

### 5.1. Objective
Initialize and configure the core Flask application, including setting up middleware, authentication, and other global settings.

### 5.2. Key Methods
- `__init__(self, config: dict)`: Initializes the plugin.
- `setup(self, app: Flask)`: Applies core configurations to the Flask app.

### 5.3. Relevant `config` Parameters
- `core_plugin`: The name of the core plugin to use (e.g., `'default_core'`).
- `server_host`: The host for the server.
- `server_port`: The port for the server.
- `debug`: Flask debug mode.
