# Prediction Provider - Files Reference Documentation

## 1. Project Structure

```
/
├── app/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── config_handler.py
│   ├── config_merger.py
│   ├── main.py
│   ├── models.py
│   └── plugin_loader.py
├── plugins_core/
│   ├── __init__.py
│   └── default_core.py
├── plugins_endpoints/
│   ├── __init__.py
│   ├── health_endpoint.py
│   ├── info_endpoint.py
│   ├── metrics_endpoint.py
│   └── predict_endpoint.py
├── plugins_feeder/
│   ├── __init__.py
│   └── default_feeder.py
├── plugins_pipeline/
│   ├── __init__.py
│   └── default_pipeline.py
├── plugins_predictor/
│   ├── __init__.py
│   └── default_predictor.py
├── examples/
│   ├── config/
│   ├── data/
│   └── results/
├── tests/
│   ├── acceptance_tests/
│   ├── integration_tests/
│   ├── system_tests/
│   └── unit_tests/
├── .gitignore
├── a_new_file.txt
├── pp.bat
├── pp.sh
├── prediction_provider.db
├── pyproject.toml
├── README.md
├── REFERENCE.md
├── REFERENCE_files.md
├── REFERNECE_plugins.md
├── requirements.txt
├── set_env.bat
├── set_env.sh
├── setup.py
└── test_service.py
```

---

## 2. `DefaultFeederPlugin` - Feature Generation & Normalization

**File:** `plugins_feeder/default_feeder.py`

This plugin is responsible for creating the exact data structure required by the `DefaultPredictorPlugin`. Its primary duties are to source raw data, compute a comprehensive set of features, and normalize the data according to a strict specification.

### Responsibilities:
1.  **Data Sourcing**: Fetches the latest raw data for the instrument specified in the configuration (e.g., `EUR/USD`). This includes:
    -   Primary time-series data (e.g., hourly `OPEN`, `HIGH`, `LOW`, `CLOSE`).
    -   High-frequency data (e.g., 15-minute and 30-minute `CLOSE` prices).
    -   Correlated market data (e.g., `S&P500_Close`, `vix_close`).
2.  **Feature Calculation**: Computes a wide range of technical indicators and derived features from the raw data. This includes all 45 columns listed in the global `REFERENCE.md`.
3.  **Normalization**: Critically, it normalizes the entire feature set using pre-defined `min` and `max` values from the JSON file specified in the `use_normalization_json` config parameter. This step is essential for the model to perform correctly.

---

## 3. `DefaultPredictorPlugin` - Model Input Requirements

**File:** `plugins_predictor/default_predictor.py`

This plugin loads the pre-trained Keras model and performs inference. It has a strict data contract and expects the input data to be in a precise format.

### Expected Input Format:
-   **Data Type**: A pandas DataFrame.
-   **Shape**: The DataFrame must have a shape of `(256, 45)`, where `256` is the `window_size` (and `batch_size`) and `45` is the number of features.
-   **Columns**: The DataFrame must contain the exact 45 feature columns as specified in the global `REFERENCE.md`, in the correct order.
-   **Normalization**: All values in the DataFrame (except for `DATE_TIME`, which should be handled appropriately) **must be min-max normalized to a `[0, 1]` range** using the official normalization parameters.

Any deviation from this format will result in either a runtime error or, worse, silent incorrect predictions. The `DefaultFeederPlugin` is designed to guarantee this contract is met.
