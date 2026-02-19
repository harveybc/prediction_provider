#!/usr/bin/env python3
"""
Noisy Ideal Predictor Plugin

Takes ideal predictions from a CSV of actual future data and adds configurable
Gaussian noise.  Designed for noise-sweep experiments to measure how prediction
quality affects strategy performance through the LTS pipeline.

Config keys:
    csv_file        (str)   – path to OHLC CSV with columns DATE_TIME, CLOSE (+ OPEN/HIGH/LOW)
    noise_std       (float) – standard deviation of Gaussian noise added to predictions (in price units)
    noise_seed      (int)   – random seed for reproducibility
    close_column    (str)   – name of the close-price column (default 'CLOSE')
    datetime_column (str)   – name of the datetime column (default 'DATE_TIME')
    hourly_horizons (int)   – number of hourly prediction horizons (default 6)
    daily_horizons  (int)   – number of daily prediction horizons (default 6)
"""

import os as _os
_QUIET = _os.environ.get('PREDICTION_PROVIDER_QUIET', '0') == '1'

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional


class NoisyIdealPredictor:
    """
    Predictor that produces ideal (look-ahead) predictions with added Gaussian noise.

    The CSV must have hourly OHLC data indexed by DATE_TIME.
    For each row, the ideal prediction at horizon *h* is simply the CLOSE value
    *h* bars ahead.  Gaussian noise with std = ``noise_std`` is then added.
    """

    plugin_params = {
        "csv_file": None,
        "noise_std": 0.0,
        "noise_seed": 42,
        "close_column": "CLOSE",
        "datetime_column": "DATE_TIME",
        "hourly_horizons": 6,
        "daily_horizons": 6,
        "prediction_horizon": 6,  # compatibility with default predictor interface
    }

    plugin_debug_vars = ["csv_file", "noise_std", "noise_seed", "hourly_horizons", "daily_horizons"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.params = self.plugin_params.copy()
        if config:
            for k, v in config.items():
                if k in self.params:
                    self.params[k] = v

        self._data: Optional[pd.DataFrame] = None
        self._rng: Optional[np.random.Generator] = None
        self._loaded = False

        if self.params["csv_file"]:
            self.load_data(self.params["csv_file"])

    # ------------------------------------------------------------------
    # Plugin interface methods
    # ------------------------------------------------------------------

    def set_params(self, **kwargs):
        for k, v in kwargs.items():
            if k in self.params:
                self.params[k] = v

    def get_debug_info(self) -> Dict[str, Any]:
        return {k: self.params.get(k) for k in self.plugin_debug_vars}

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_data(self, csv_file: str):
        """Load OHLC data from *csv_file*."""
        if not _os.path.exists(csv_file):
            raise FileNotFoundError(f"CSV file not found: {csv_file}")

        dt_col = self.params["datetime_column"]
        df = pd.read_csv(csv_file)
        df[dt_col] = pd.to_datetime(df[dt_col])
        df.set_index(dt_col, inplace=True)
        df.sort_index(inplace=True)
        self._data = df
        self._rng = np.random.default_rng(self.params["noise_seed"])
        self._loaded = True

    @property
    def data_loaded(self) -> bool:
        return self._loaded

    # ------------------------------------------------------------------
    # Prediction generation
    # ------------------------------------------------------------------

    def predict_at(self, timestamp: pd.Timestamp) -> Dict[str, Any]:
        """
        Generate noisy ideal predictions for every configured horizon at *timestamp*.

        Returns dict with keys:
            hourly_predictions  – list of floats (predicted prices, 1h..Nh)
            daily_predictions   – list of floats (predicted prices, 1d..Nd)
            timestamp           – ISO string of the reference timestamp
            noise_std           – noise std used
        """
        if self._data is None:
            raise RuntimeError("Data not loaded – call load_data first")

        ts = pd.Timestamp(timestamp)
        idx = self._data.index.get_indexer([ts], method="nearest")[0]
        close_col = self.params["close_column"]
        noise_std = self.params["noise_std"]

        hourly_preds = []
        for h in range(1, self.params["hourly_horizons"] + 1):
            fi = idx + h
            if fi < len(self._data):
                ideal = float(self._data.iloc[fi][close_col])
            else:
                ideal = float(self._data.iloc[idx][close_col])
            noisy = ideal + self._rng.normal(0, noise_std) if noise_std > 0 else ideal
            hourly_preds.append(noisy)

        daily_preds = []
        for d in range(1, self.params["daily_horizons"] + 1):
            fi = idx + d * 24  # assuming hourly data
            if fi < len(self._data):
                ideal = float(self._data.iloc[fi][close_col])
            else:
                ideal = float(self._data.iloc[idx][close_col])
            noisy = ideal + self._rng.normal(0, noise_std) if noise_std > 0 else ideal
            daily_preds.append(noisy)

        return {
            "hourly_predictions": hourly_preds,
            "daily_predictions": daily_preds,
            "timestamp": self._data.index[idx].isoformat(),
            "noise_std": noise_std,
        }

    def generate_all_predictions(self) -> Dict[str, pd.DataFrame]:
        """
        Generate prediction DataFrames for *every* timestamp in the loaded data.

        Returns dict with:
            hourly – DataFrame indexed by DATE_TIME, columns Prediction_h_1 .. Prediction_h_N
            daily  – DataFrame indexed by DATE_TIME, columns Prediction_d_1 .. Prediction_d_N

        These DataFrames are in the format expected by the heuristic-strategy plugin.
        """
        if self._data is None:
            raise RuntimeError("Data not loaded")

        # Reset RNG for reproducibility
        self._rng = np.random.default_rng(self.params["noise_seed"])

        close_col = self.params["close_column"]
        noise_std = self.params["noise_std"]
        n_hourly = self.params["hourly_horizons"]
        n_daily = self.params["daily_horizons"]
        n = len(self._data)

        h_cols = [f"Prediction_h_{i+1}" for i in range(n_hourly)]
        d_cols = [f"Prediction_d_{i+1}" for i in range(n_daily)]

        h_arr = np.full((n, n_hourly), np.nan)
        d_arr = np.full((n, n_daily), np.nan)

        closes = self._data[close_col].values.astype(float)

        for row in range(n):
            for h in range(n_hourly):
                fi = row + h + 1
                ideal = closes[fi] if fi < n else closes[row]
                h_arr[row, h] = ideal + self._rng.normal(0, noise_std) if noise_std > 0 else ideal

            for d in range(n_daily):
                fi = row + (d + 1) * 24
                ideal = closes[fi] if fi < n else closes[row]
                d_arr[row, d] = ideal + self._rng.normal(0, noise_std) if noise_std > 0 else ideal

        hourly_df = pd.DataFrame(h_arr, index=self._data.index, columns=h_cols)
        daily_df = pd.DataFrame(d_arr, index=self._data.index, columns=d_cols)

        return {"hourly": hourly_df, "daily": daily_df}

    # ------------------------------------------------------------------
    # Prediction provider API compatibility
    # ------------------------------------------------------------------

    def predict(self, input_data: Any = None, **kwargs) -> Dict[str, Any]:
        """
        Compatibility method for the prediction provider pipeline.

        If *input_data* is a dict with 'timestamp', generates predictions at that time.
        Otherwise generates predictions for the first available timestamp.
        """
        if isinstance(input_data, dict) and "timestamp" in input_data:
            ts = pd.Timestamp(input_data["timestamp"])
        elif isinstance(input_data, (str, pd.Timestamp)):
            ts = pd.Timestamp(input_data)
        else:
            ts = self._data.index[0] if self._data is not None else None

        if ts is None:
            raise ValueError("No timestamp provided and no data loaded")

        result = self.predict_at(ts)

        # Return in prediction provider format
        return {
            "prediction": result["hourly_predictions"],
            "daily_prediction": result["daily_predictions"],
            "timestamp": result["timestamp"],
            "model_name": "noisy_ideal_predictor",
            "noise_std": result["noise_std"],
        }
