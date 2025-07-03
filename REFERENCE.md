# Prediction Provider - Global Reference Documentation

## 1. System Architecture and Workflow

The Prediction Provider is a modular, plugin-based API service designed for real-time machine learning prediction workflows. It is built with a focus on flexibility, scalability, and maintainability, allowing developers to dynamically extend its functionality by adding new plugins.

### 1.1. Core Principles
- **Plugin-Based Architecture**: The system is composed of five distinct plugin types: `core`, `endpoints`, `feeder`, `predictor`, and `pipeline`. This modularity allows for independent development, testing, and deployment of different functionalities.
- **Dynamic Plugin Loading**: Plugins are discovered and loaded at runtime based on the application's configuration, enabling seamless integration of new capabilities without code modifications to the core system.
- **Asynchronous Prediction**: Prediction requests are handled asynchronously in background threads, ensuring the API remains responsive and can manage long-running inference tasks.
- **Separation of Concerns**: Each component and plugin type has a single, well-defined responsibility, from data acquisition and feature engineering to model inference and API exposure.
- **Database Integration**: The system uses SQLAlchemy for database interactions, primarily for persisting prediction requests, tracking their status, and storing results.

### 1.2. Standard Workflow
1.  **Initialization**: The application starts via `app/main.py`, which parses arguments and loads the default configuration from `app/config.py`.
2.  **Configuration Merging**: It merges configurations from multiple sources (default, file, CLI) to create the final runtime configuration.
3.  **Plugin Loading**: All required plugins (`core`, `endpoints`, `feeder`, `predictor`, `pipeline`) are dynamically loaded based on the configuration.
4.  **Server Setup**: The `core` plugin initializes the Flask web server, applying global settings like authentication and CORS.
5.  **Endpoint Registration**: `endpoint` plugins register their specific RESTful API routes (e.g., `/predict`, `/health`).
6.  **API Request**: An external client sends a prediction request to an endpoint (e.g., `/predict`).
7.  **Data Fetching**: The `feeder` plugin is invoked to fetch the latest required data from external sources (e.g., financial APIs).
8.  **Feature Engineering & Normalization**: The `feeder` calculates all derived technical indicators and high-frequency features. It then normalizes the entire feature set using pre-defined parameters from a JSON file.
9.  **Prediction**: The `predictor` plugin loads the specified machine learning model and performs inference on the prepared data.
10. **Response**: The prediction result is returned to the client, and the request/result may be logged to the database.

---

## 2. Main Configuration Parameters

The following are the key global configuration parameters, primarily defined in `app/config.py`. Default values are shown below.

| Parameter | Default Value | Description |
| --- | --- | --- |
| **Server & Database** | | |
| `server_host` | `'0.0.0.0'` | The host address for the Flask server. |
| `server_port` | `5000` | The port for the Flask server. |
| `debug` | `False` | Enables or disables Flask's debug mode. |
| `database_url` | `'sqlite:///predictions.db'` | The connection string for the SQLAlchemy database. |
| **Plugins** | | |
| `pipeline_plugin` | `'default_pipeline'` | The default pipeline plugin to use. |
| `feeder_plugin` | `'default_feeder'` | The default data feeder plugin to use. |
| `predictor_plugin`| `'default_predictor'` | The default predictor plugin to use. |
| `endpoint_plugins`| `['predict_endpoint']` | A list of endpoint plugins to load. |
| `core_plugin` | `'default_core'` | The default core plugin for Flask app initialization. |
| **Data Feeder** | | |
| `instrument` | `'EUR/USD'` | The financial instrument to fetch data for. |
| `n_batches` | `1` | The number of batches to retrieve. Total records = `n_batches` * `batch_size`. |
| `batch_size` | `256` | The number of time steps (records) in each batch. |
| `use_normalization_json` | `examples/config/phase_2_normalizer_debug_out.json` | Path to the JSON file containing min/max values for data normalization. **Crucial for correct model input.** |
| **Predictor** | | |
| `model_path` | `'./predictor_model.keras'` | The file path to the trained Keras model. |
| `window_size` | `256` | The number of time steps required by the model for a single prediction. Must match `batch_size`. |
| `target_column` | `'CLOSE'` | The name of the target variable for prediction. |
| `mc_samples` | `100` | The number of Monte Carlo samples for uncertainty estimation. |

---

## 3. Default Model - Required Feature Set

The default predictor plugin (`default_predictor`) requires a precise set of input features, which the `default_feeder` plugin is responsible for generating and normalizing. The data must be provided in a pandas DataFrame with the exact column names and order listed below.

### 3.1. Data Normalization
All feature values **must be min-max normalized** to a `[0, 1]` range. The normalization **must** use the specific `min` and `max` values stored in the JSON file defined by the `use_normalization_json` configuration parameter. This ensures that the data fed to the model has the same distribution as the data it was trained on.

### 3.2. Required Columns
The DataFrame fed to the model must contain the following 45 columns:

| # | Column Name | Data Source / Calculation |
|---|---|---|
| 1 | `DATE_TIME` | Primary timestamp (e.g., hourly). |
| 2 | `RSI` | Calculated from `CLOSE` prices. |
| 3 | `MACD` | Calculated from `CLOSE` prices. |
| 4 | `MACD_Histogram` | Calculated from `MACD` and `MACD_Signal`. |
| 5 | `MACD_Signal` | Calculated from `MACD`. |
| 6 | `EMA` | Calculated from `CLOSE` prices. |
| 7 | `Stochastic_%K` | Calculated from `HIGH`, `LOW`, `CLOSE`. |
| 8 | `Stochastic_%D` | Calculated from `Stochastic_%K`. |
| 9 | `ADX` | Calculated from `HIGH`, `LOW`, `CLOSE`. |
| 10 | `DI+` | Component of ADX. |
| 11 | `DI-` | Component of ADX. |
| 12 | `ATR` | Calculated from `HIGH`, `LOW`, `CLOSE`. |
| 13 | `CCI` | Calculated from `HIGH`, `LOW`, `CLOSE`. |
| 14 | `WilliamsR` | Calculated from `HIGH`, `LOW`, `CLOSE`. |
| 15 | `Momentum` | Calculated from `CLOSE` prices. |
| 16 | `ROC` | Calculated from `CLOSE` prices. |
| 17 | `OPEN` | Sourced directly (e.g., EUR/USD hourly). |
| 18 | `HIGH` | Sourced directly (e.g., EUR/USD hourly). |
| 19 | `LOW` | Sourced directly (e.g., EUR/USD hourly). |
| 20 | `CLOSE` | Sourced directly (e.g., EUR/USD hourly). |
| 21 | `BC-BO` | `CLOSE` - `OPEN` of the previous bar. |
| 22 | `BH-BL` | `HIGH` - `LOW` of the previous bar. |
| 23 | `BH-BO` | `HIGH` - `OPEN` of the previous bar. |
| 24 | `BO-BL` | `OPEN` - `LOW` of the previous bar. |
| 25 | `S&P500_Close` | Sourced from external API (daily or hourly). |
| 26 | `vix_close` | Sourced from external API (daily or hourly). |
| 27 | `CLOSE_15m_tick_1` | Close price from 15 minutes ago. |
| 28 | `CLOSE_15m_tick_2` | Close price from 30 minutes ago. |
| 29 | `CLOSE_15m_tick_3` | Close price from 45 minutes ago. |
| 30 | `CLOSE_15m_tick_4` | Close price from 60 minutes ago. |
| 31 | `CLOSE_15m_tick_5` | Close price from 75 minutes ago. |
| 32 | `CLOSE_15m_tick_6` | Close price from 90 minutes ago. |
| 33 | `CLOSE_15m_tick_7` | Close price from 105 minutes ago. |
| 34 | `CLOSE_15m_tick_8` | Close price from 120 minutes ago. |
| 35 | `CLOSE_30m_tick_1` | Close price from 30 minutes ago. |
| 36 | `CLOSE_30m_tick_2` | Close price from 60 minutes ago. |
| 37 | `CLOSE_30m_tick_3` | Close price from 90 minutes ago. |
| 38 | `CLOSE_30m_tick_4` | Close price from 120 minutes ago. |
| 39 | `CLOSE_30m_tick_5` | Close price from 150 minutes ago. |
| 40 | `CLOSE_30m_tick_6` | Close price from 180 minutes ago. |
| 41 | `CLOSE_30m_tick_7` | Close price from 210 minutes ago. |
| 42 | `CLOSE_30m_tick_8` | Close price from 240 minutes ago. |
| 43 | `day_of_month` | Calculated from `DATE_TIME`. |
| 44 | `hour_of_day` | Calculated from `DATE_TIME`. |
| 45 | `day_of_week` | Calculated from `DATE_TIME`. |
