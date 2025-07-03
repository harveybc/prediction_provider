# Prediction Provider - File-Level Reference

## 1. `DefaultFeederPlugin` - Feature Generation & Normalization

**File:** `feeder_plugins/default_feeder.py`

This plugin is responsible for creating the exact data structure required by the `DefaultPredictorPlugin`. Its primary duties are to source raw data, compute a comprehensive set of features, and normalize the data according to a strict specification.

### Responsibilities:
1.  **Data Sourcing**: Fetches the latest raw data for the instrument specified in the configuration (e.g., `EUR/USD`). This includes:
    -   Primary time-series data (e.g., hourly `OPEN`, `HIGH`, `LOW`, `CLOSE`).
    -   High-frequency data (e.g., 15-minute and 30-minute `CLOSE` prices).
    -   Correlated market data (e.g., `S&P500_Close`, `vix_close`).
2.  **Feature Calculation**: Computes a wide range of technical indicators and derived features from the raw data. This includes all 45 columns listed in the global `REFERENCE.md`.
3.  **Normalization**: Critically, it normalizes the entire feature set using pre-defined `min` and `max` values from the JSON file specified in the `use_normalization_json` config parameter. This step is essential for the model to perform correctly.

---

## 2. `DefaultPredictorPlugin` - Model Input Requirements

**File:** `predictor_plugins/default_predictor.py`

This plugin loads the pre-trained Keras model and performs inference. It has a strict data contract and expects the input data to be in a precise format.

### Expected Input Format:
-   **Data Type**: A pandas DataFrame.
-   **Shape**: The DataFrame must have a shape of `(256, 45)`, where `256` is the `window_size` (and `batch_size`) and `45` is the number of features.
-   **Columns**: The DataFrame must contain the exact 45 feature columns as specified in the global `REFERENCE.md`, in the correct order.
-   **Normalization**: All values in the DataFrame (except for `DATE_TIME`, which should be handled appropriately) **must be min-max normalized to a `[0, 1]` range** using the official normalization parameters.

Any deviation from this format will result in either a runtime error or, worse, silent incorrect predictions. The `DefaultFeederPlugin` is designed to guarantee this contract is met.
