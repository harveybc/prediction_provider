#!/usr/bin/env python3
"""
Binary Exit Predictor Plugin (Inference Only)

Loads a pre-trained Keras model (produced by the predictor repo) and uses
it for binary exit inference.  The model predicts whether TP is still
reachable for an open position.

This plugin does NOT define model architecture or train — the predictor
repo handles model building, training, and hyperparameter optimization.

Expected model contract (from predictor repo):
  - Input:  (batch, window_size, n_features) float32
  - Output: (batch, 1) float32 — keep_open probability in [0,1]
  Note: the predictor repo exit model may include direction/tp_dist/sl_dist
  as extra input features appended to the feature window.

Metadata JSON must contain: feature_columns (list[str]), window_size (int).

Config keys:
    model_path            (str)   – path to .keras model file
    csv_file              (str)   – path to CSV for OHLC+features lookback
    window_size           (int)   – overridden by metadata if available
    mc_samples            (int)   – MC dropout samples for uncertainty (0=off)
    confidence_threshold  (float) – min prob to keep open (default 0.5)
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


class BinaryExitPredictor:
    """Inference-only predictor for binary exit (early-close) signals."""

    plugin_params = {
        "model_path": None,
        "csv_file": None,
        "window_size": 32,
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
        """Load a pre-trained Keras model for exit prediction."""
        import tensorflow as tf

        if not _os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")

        self._model = tf.keras.models.load_model(model_path)
        if not _QUIET:
            print(f"[BinaryExitPredictor] Loaded model from {model_path}")

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
                print(f"[BinaryExitPredictor] Metadata: window={self.params['window_size']}, "
                      f"features={len(self._feature_cols)}")

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

        if not self._feature_cols:
            exclude = {'OPEN', 'HIGH', 'LOW', 'CLOSE',
                       'buy_entry_label', 'sell_entry_label',
                       'buy_exit_label', 'sell_exit_label',
                       'bars_to_friday'}
            self._feature_cols = [c for c in df.columns if c not in exclude]

        if not _QUIET:
            print(f"[BinaryExitPredictor] Loaded {len(df)} rows, "
                  f"{len(self._feature_cols)} feature columns")

    # ------------------------------------------------------------------
    # Entry prediction (stub — no signal)
    # ------------------------------------------------------------------

    def predict_entry(self, timestamp, tp_pips: float = 0.0,
                      sl_pips: float = 0.0, spread_pips: float = 0.0,
                      commission_per_lot: float = 0.0,
                      slippage_pips: float = 0.0) -> Dict[str, Any]:
        """Stub: no entry signal. Use BinaryEntryPredictor for entry."""
        return {
            "buy_entry_binary": 0.0, "sell_entry_binary": 0.0,
            "bars_remaining": 0,
            "buy_confidence": 0.0, "sell_confidence": 0.0,
            "timestamp": str(pd.Timestamp(timestamp)), "current_price": 0.0,
        }

    # ------------------------------------------------------------------
    # Exit prediction (inference only)
    # ------------------------------------------------------------------

    def predict_exit(self, timestamp, direction: str,
                     tp_price: float, sl_price: float) -> Dict[str, Any]:
        """Run inference to predict whether to close an open position early.

        Returns exit_binary=1 (keep open) or 0 (close early).
        """
        if self._data is None:
            raise RuntimeError("Data not loaded — call load_data first")

        ts = pd.Timestamp(timestamp)
        idx = self._data.index.get_indexer([ts], method='ffill')[0]
        if idx < 0:
            idx = 0

        current_price = float(self._data.iloc[idx][self.params['close_column']])

        # No model loaded → keep open (safe default)
        if self._model is None:
            return {
                "exit_binary": 1.0, "exit_confidence": 0.0,
                "timestamp": str(ts), "current_price": current_price,
            }

        # Build feature window
        window_size = int(self.params['window_size'])
        start = max(0, idx - window_size + 1)
        window = self._data.iloc[start:idx + 1]

        feat_cols = [c for c in self._feature_cols if c in window.columns]
        X = window[feat_cols].values.astype(np.float32)

        # Append direction + TP/SL distance as extra features
        # (the exit model from predictor repo is trained with these)
        pip = float(self.params['pip_cost'])
        direction_feat = 1.0 if direction == 'buy' else -1.0
        tp_dist = abs(tp_price - current_price) / pip if pip > 0 else 0.0
        sl_dist = abs(sl_price - current_price) / pip if pip > 0 else 0.0
        extra = np.full((X.shape[0], 3), [direction_feat, tp_dist, sl_dist], dtype=np.float32)
        X = np.hstack([X, extra])

        # Pad if window too short
        if X.shape[0] < window_size:
            pad = np.zeros((window_size - X.shape[0], X.shape[1]), dtype=np.float32)
            X = np.vstack([pad, X])

        X_input = X.reshape(1, window_size, -1)

        # Inference
        if self.params['mc_samples'] > 0:
            preds = np.array([
                self._model(X_input, training=True).numpy()
                for _ in range(self.params['mc_samples'])
            ])
            mean_pred = float(preds.mean())
            std_pred = float(preds.std())
            confidence = max(0.0, 1.0 - 2.0 * std_pred)
        else:
            pred = self._model.predict(X_input, verbose=0)
            mean_pred = float(pred[0][0])
            confidence = 1.0

        threshold = float(self.params['confidence_threshold'])
        return {
            "exit_binary": 1.0 if mean_pred >= threshold else 0.0,
            "exit_confidence": confidence,
            "timestamp": str(ts),
            "current_price": current_price,
        }

    # ------------------------------------------------------------------
    # Model info
    # ------------------------------------------------------------------

    def get_model_info(self) -> Dict[str, Any]:
        n_base = len(self._feature_cols)
        return {
            "model_name": "binary_exit_predictor",
            "window_size": self.params["window_size"],
            "supported_types": ["exit"],
            "entry_directions": [],
            "exit_directions": ["buy", "sell"],
            "prediction_scope": "short_term",
            "required_columns": self._feature_cols[:10] if self._feature_cols else ["OPEN", "HIGH", "LOW", "CLOSE"],
            "accepts_ohlc_window": True,
            "extra_exit_features": ["direction", "tp_distance_pips", "sl_distance_pips"],
            "total_features": n_base + 3,
        }


Plugin = BinaryExitPredictor
