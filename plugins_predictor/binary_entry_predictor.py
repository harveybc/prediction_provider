#!/usr/bin/env python3
"""
Binary Entry Predictor Plugin (Inference Only)

Loads a pre-trained Keras model (produced by the predictor repo) and uses
it for binary entry inference.  The model outputs buy/sell probabilities;
this plugin thresholds them and returns binary signals + confidence to
sync_core.

This plugin does NOT define model architecture or train — the predictor
repo handles model building, training, and hyperparameter optimization.

Expected model contract (from predictor repo):
  - Input:  (batch, window_size, n_features) float32
  - Output: (batch, 2) float32 — [buy_prob, sell_prob] in [0,1]

Metadata JSON (produced alongside the model) must contain:
  feature_columns (list[str]), window_size (int).

Config keys:
    model_path            (str)   – path to .keras model file
    csv_file              (str)   – path to CSV for OHLC+features lookback
    window_size           (int)   – overridden by metadata if available
    mc_samples            (int)   – MC dropout samples for uncertainty (0=off)
    confidence_threshold  (float) – min prob to emit signal (default 0.5)
    normalization_params_path (str) – optional JSON with {col: {mean, std}}
    pip_cost              (float) – one pip in price units
    friday_close_hour     (int)   – trading-week close hour
    prediction_horizon    (int)   – fallback horizon in bars
"""

import os as _os
_QUIET = _os.environ.get('PREDICTION_PROVIDER_QUIET', '0') == '1'

import numpy as np
import pandas as pd
import json
from typing import Dict, Any, Optional, List


class BinaryEntryPredictor:
    """Inference-only predictor for binary entry signals (buy/sell)."""

    plugin_params = {
        "model_path": None,
        "csv_file": None,
        "window_size": 64,
        "mc_samples": 0,
        "confidence_threshold": 0.5,
        "close_column": "CLOSE",
        "high_column": "HIGH",
        "low_column": "LOW",
        "datetime_column": "DATE_TIME",
        "pip_cost": 0.00001,
        "prediction_horizon": 120,
        "friday_close_hour": 20,
        "normalization_params_path": None,
    }

    plugin_debug_vars = [
        "model_path", "csv_file", "window_size", "mc_samples",
        "pip_cost", "friday_close_hour", "confidence_threshold",
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.params = self.plugin_params.copy()
        if config:
            for k, v in config.items():
                if k in self.params:
                    self.params[k] = v

        self._model = None
        self._data: Optional[pd.DataFrame] = None
        self._feature_cols: List[str] = []
        self._normalization_params = None

        if self.params["model_path"]:
            self.load_model(self.params["model_path"])
        if self.params["csv_file"]:
            self.load_data(self.params["csv_file"])

    # ------------------------------------------------------------------
    # Plugin interface
    # ------------------------------------------------------------------

    def set_params(self, **kwargs):
        for k, v in kwargs.items():
            if k in self.params:
                self.params[k] = v

    def get_debug_info(self) -> Dict[str, Any]:
        info = {k: self.params.get(k) for k in self.plugin_debug_vars}
        info["model_loaded"] = self._model is not None
        info["data_loaded"] = self._data is not None
        info["n_features"] = len(self._feature_cols)
        return info

    # ------------------------------------------------------------------
    # Model loading (pre-trained .keras — no architecture defined here)
    # ------------------------------------------------------------------

    def load_model(self, model_path: str):
        """Load a pre-trained Keras model for entry prediction."""
        import tensorflow as tf

        if not _os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")

        self._model = tf.keras.models.load_model(model_path)
        if not _QUIET:
            print(f"[BinaryEntryPredictor] Loaded model from {model_path}")

        # Load metadata (feature_columns, window_size) produced by predictor repo
        base = model_path.rsplit('.', 1)[0]
        meta_path = base + '_metadata.json'
        if _os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
            if 'feature_columns' in meta:
                self._feature_cols = meta['feature_columns']
            if 'window_size' in meta:
                self.params['window_size'] = meta['window_size']
            if not _QUIET:
                print(f"[BinaryEntryPredictor] Metadata: window={self.params['window_size']}, "
                      f"features={len(self._feature_cols)}")

        # Load normalization params if available
        norm_path = self.params.get("normalization_params_path")
        if norm_path and _os.path.exists(norm_path):
            with open(norm_path) as f:
                self._normalization_params = json.load(f)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_data(self, csv_file: str):
        """Load OHLC + features CSV for windowed lookback."""
        if not _os.path.exists(csv_file):
            raise FileNotFoundError(f"CSV file not found: {csv_file}")

        df = pd.read_csv(csv_file)
        dt_col = self.params["datetime_column"]
        if dt_col in df.columns:
            df[dt_col] = pd.to_datetime(df[dt_col])
            df.set_index(dt_col, inplace=True)
        df.sort_index(inplace=True)
        self._data = df

        # Auto-discover feature columns if not set from metadata
        if not self._feature_cols:
            exclude = {'OPEN', 'HIGH', 'LOW', 'CLOSE',
                       'buy_entry_label', 'sell_entry_label',
                       'buy_exit_label', 'sell_exit_label',
                       'bars_to_friday'}
            self._feature_cols = [c for c in df.columns if c not in exclude]

        if not _QUIET:
            print(f"[BinaryEntryPredictor] Loaded {len(df)} rows, "
                  f"{len(self._feature_cols)} feature columns")

    # ------------------------------------------------------------------
    # Entry prediction (inference only)
    # ------------------------------------------------------------------

    def predict_entry(self, timestamp, tp_pips: float = 0.0,
                      sl_pips: float = 0.0, spread_pips: float = 0.0,
                      commission_per_lot: float = 0.0,
                      slippage_pips: float = 0.0) -> Dict[str, Any]:
        """Run inference on pre-trained model to predict buy/sell entry."""
        if self._data is None:
            raise RuntimeError("Data not loaded — call load_data first")

        ts = pd.Timestamp(timestamp)
        idx = self._data.index.get_indexer([ts], method='ffill')[0]
        if idx < 0:
            idx = 0

        current_price = float(self._data.iloc[idx][self.params['close_column']])
        bars_remaining = self._bars_to_friday_close(idx)

        # No model loaded → neutral
        if self._model is None:
            return {
                "buy_entry_binary": 0.0, "sell_entry_binary": 0.0,
                "bars_remaining": bars_remaining,
                "buy_confidence": 0.0, "sell_confidence": 0.0,
                "timestamp": str(ts), "current_price": current_price,
            }

        # Build feature window
        window_size = int(self.params['window_size'])
        start = max(0, idx - window_size + 1)
        window = self._data.iloc[start:idx + 1]

        feat_cols = [c for c in self._feature_cols if c in window.columns]
        X = window[feat_cols].values.astype(np.float32)

        # Pad if window too short
        if X.shape[0] < window_size:
            pad = np.zeros((window_size - X.shape[0], X.shape[1]), dtype=np.float32)
            X = np.vstack([pad, X])

        X_input = X.reshape(1, window_size, -1)

        # Inference (MC dropout for uncertainty or single-pass)
        if self.params['mc_samples'] > 0:
            preds = np.array([
                self._model(X_input, training=True).numpy()
                for _ in range(self.params['mc_samples'])
            ])
            mean_pred = preds.mean(axis=0)[0]
            std_pred = preds.std(axis=0)[0]
            buy_conf = float(max(0.0, 1.0 - 2.0 * std_pred[0]))
            sell_conf = float(max(0.0, 1.0 - 2.0 * std_pred[1]))
        else:
            pred = self._model.predict(X_input, verbose=0)
            mean_pred = pred[0]
            buy_conf = 1.0
            sell_conf = 1.0

        threshold = float(self.params['confidence_threshold'])
        return {
            "buy_entry_binary": 1.0 if mean_pred[0] >= threshold else 0.0,
            "sell_entry_binary": 1.0 if mean_pred[1] >= threshold else 0.0,
            "bars_remaining": bars_remaining,
            "buy_confidence": buy_conf,
            "sell_confidence": sell_conf,
            "timestamp": str(ts),
            "current_price": current_price,
        }

    # ------------------------------------------------------------------
    # Exit prediction (stub — delegate to BinaryExitPredictor)
    # ------------------------------------------------------------------

    def predict_exit(self, timestamp, direction: str,
                     tp_price: float, sl_price: float) -> Dict[str, Any]:
        """Stub: keep-open. Use BinaryExitPredictor or BinaryPredictor for exit."""
        return {
            "exit_binary": 1.0, "exit_confidence": 1.0,
            "timestamp": str(pd.Timestamp(timestamp)), "current_price": 0.0,
        }

    # ------------------------------------------------------------------
    # Model info
    # ------------------------------------------------------------------

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "model_name": "binary_entry_predictor",
            "window_size": self.params["window_size"],
            "supported_types": ["entry"],
            "entry_directions": ["buy", "sell"],
            "exit_directions": [],
            "prediction_scope": "weekly",
            "required_columns": self._feature_cols[:10] if self._feature_cols else ["OPEN", "HIGH", "LOW", "CLOSE"],
            "accepts_ohlc_window": True,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _bars_to_friday_close(self, idx: int) -> int:
        if self._data is None:
            return int(self.params['prediction_horizon'])
        friday_hour = int(self.params['friday_close_hour'])
        n = len(self._data)
        dt = self._data.index[idx]
        if hasattr(dt, 'weekday') and dt.weekday() == 4 and dt.hour >= friday_hour:
            return 0
        bars = 0
        for j in range(idx + 1, min(idx + 200, n)):
            bars += 1
            jdt = self._data.index[j]
            if hasattr(jdt, 'weekday') and jdt.weekday() == 4 and jdt.hour >= friday_hour:
                break
        return bars if bars > 0 else int(self.params['prediction_horizon'])


Plugin = BinaryEntryPredictor
