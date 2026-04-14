#!/usr/bin/env python3
"""
Direction Predictor Plugin (Inference Only)

Loads TWO pre-trained direction classification models:
  1. direction_long  model → P(price goes up over long horizon)
  2. direction_short model → P(price goes up over short horizon)

Maps the single sigmoid output to buy/sell signals:
  P(up) > threshold → buy_entry, sell_exit
  P(up) < (1 - threshold) → sell_entry, buy_exit

This is the prediction_provider counterpart to the predictor repo's
direction_* plugins.  It does NOT define model architecture — instead
it rebuilds the architecture using the predictor repo's plugin system
and loads weights.

Config keys:
    long_model_path       (str)   – path to direction_long .keras
    short_model_path      (str)   – path to direction_short .keras
    csv_file              (str)   – path to CSV for OHLC+features lookback
    window_size           (int)   – overridden by metadata if available
    mc_samples            (int)   – MC dropout samples for uncertainty (0=off)
    confidence_threshold  (float) – min prob to emit signal (default 0.55)
    normalization_params_path (str) – optional JSON with {col: {mean, std}}
"""

import os as _os
_QUIET = _os.environ.get('PREDICTION_PROVIDER_QUIET', '0') == '1'

import numpy as np
import pandas as pd
import json
from typing import Dict, Any, Optional, List


class DirectionPredictor:
    """Inference-only predictor for direction classification signals."""

    plugin_params = {
        "long_model_path": None,
        "short_model_path": None,
        "csv_file": None,
        "window_size": 72,
        "mc_samples": 0,
        "confidence_threshold": 0.55,
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
        "long_model_path", "short_model_path", "csv_file",
        "window_size", "mc_samples", "confidence_threshold",
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.params = self.plugin_params.copy()
        if config:
            for k, v in config.items():
                if k in self.params:
                    self.params[k] = v

        self._long_model = None
        self._short_model = None
        self._data: Optional[pd.DataFrame] = None
        self._feature_cols: List[str] = []
        self._normalization_params = None

        if self.params["long_model_path"]:
            self._long_model = self._load_direction_model(
                self.params["long_model_path"], "long"
            )
        if self.params["short_model_path"]:
            self._short_model = self._load_direction_model(
                self.params["short_model_path"], "short"
            )
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
        info["long_model_loaded"] = self._long_model is not None
        info["short_model_loaded"] = self._short_model is not None
        info["data_loaded"] = self._data is not None
        info["n_features"] = len(self._feature_cols)
        return info

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_direction_model(self, model_path: str, label: str):
        """Load a pre-trained direction classification model.

        Uses the same rebuild-from-zip approach as binary_entry_predictor:
        extract architecture from config.json, rebuild, load weights.
        """
        import tensorflow as tf
        import zipfile
        import tempfile

        if not _os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")

        # Load metadata
        base = model_path.rsplit('.', 1)[0]
        meta_path = base + '_metadata.json'
        if _os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
            if 'feature_columns' in meta and not self._feature_cols:
                self._feature_cols = meta['feature_columns']
            if 'window_size' in meta:
                self.params['window_size'] = meta['window_size']
            if not _QUIET:
                print(f"[DirectionPredictor:{label}] Metadata: "
                      f"window={self.params['window_size']}, "
                      f"features={len(self._feature_cols)}")

        # Extract arch params from .keras zip
        arch_params = self._extract_arch_params(model_path)

        # Rebuild architecture generically
        window_size = int(self.params['window_size'])
        n_features = (len(self._feature_cols) if self._feature_cols
                      else arch_params.get('n_features', 22))
        model = self._rebuild_generic_model(
            model_path, window_size, n_features, arch_params
        )

        # Load weights
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(model_path, 'r') as zf:
                zf.extractall(tmpdir)
            weights_path = _os.path.join(tmpdir, 'model.weights.h5')
            if not _os.path.exists(weights_path):
                raise FileNotFoundError(
                    f"No model.weights.h5 inside {model_path}")
            model.load_weights(weights_path)

        if not _QUIET:
            print(f"[DirectionPredictor:{label}] Loaded from {model_path}")

        # Load normalization if available
        norm_path = self.params.get("normalization_params_path")
        if norm_path and _os.path.exists(norm_path) and not self._normalization_params:
            with open(norm_path) as f:
                self._normalization_params = json.load(f)

        return model

    @staticmethod
    def _extract_arch_params(keras_path: str) -> dict:
        """Read config.json inside a .keras zip to infer architecture."""
        import zipfile
        with zipfile.ZipFile(keras_path, 'r') as zf:
            config = json.loads(zf.read('config.json'))

        layers = config.get('config', {}).get('layers', [])
        params: Dict[str, Any] = {}
        params['model_name'] = config.get('config', {}).get('name', '')

        for layer in layers:
            cls = layer.get('class_name', '')
            cfg = layer.get('config', {})
            if cls == 'Lambda':
                build_cfg = cfg.get('build_config', {})
                input_shape = build_cfg.get('input_shape', [None, 72, 22])
                if input_shape and len(input_shape) == 3:
                    params['n_features'] = input_shape[2]
            elif cls == 'InputLayer':
                shape = cfg.get('batch_shape', [None, 72, 22])
                if shape and len(shape) == 3:
                    params['n_features'] = shape[2]

        return params

    @staticmethod
    def _rebuild_generic_model(keras_path: str, window_size: int,
                                n_features: int, arch_params: dict):
        """Rebuild ANY direction model by using predictor repo plugin system.

        Attempts to load the predictor plugin specified in the model name
        and calls build_model().  Falls back to loading directly with
        tf.keras.models.load_model (works for models without Lambda layers).
        """
        import tensorflow as tf

        model_name = arch_params.get('model_name', '')

        # Try to discover and use the predictor plugin for architecture
        plugin_name = None
        for prefix in ['Direction', 'direction_']:
            if model_name.startswith(prefix):
                # e.g. "DirectionTFT_direction_long" → "direction_tft"
                rest = model_name[len(prefix):]
                arch = rest.split('_')[0].lower()
                plugin_name = f"direction_{arch}"
                break

        if plugin_name:
            try:
                from importlib.metadata import entry_points
                eps = entry_points()
                if hasattr(eps, 'select'):
                    matches = eps.select(group='predictor.plugins', name=plugin_name)
                else:
                    matches = [ep for ep in eps.get('predictor.plugins', [])
                               if ep.name == plugin_name]
                for ep in matches:
                    plugin_cls = ep.load()
                    plugin = plugin_cls()
                    plugin.build_model(
                        (window_size, n_features),
                        x_train=np.zeros((1, window_size, n_features)),
                        config={'quiet': True},
                    )
                    if not _QUIET:
                        print(f"[DirectionPredictor] Rebuilt via plugin '{plugin_name}'")
                    return plugin.model
            except Exception as e:
                if not _QUIET:
                    print(f"[DirectionPredictor] Plugin rebuild failed ({e}), "
                          f"trying direct load")

        # Fallback: direct load (works for models without Lambda closures)
        try:
            model = tf.keras.models.load_model(keras_path)
            if not _QUIET:
                print(f"[DirectionPredictor] Loaded model directly")
            return model
        except Exception:
            raise RuntimeError(
                f"Cannot rebuild model '{model_name}' — "
                f"install predictor repo with direction plugins"
            )

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
                       'direction_long_label', 'direction_short_label',
                       'bars_to_friday'}
            self._feature_cols = [c for c in df.columns if c not in exclude]

        if not _QUIET:
            print(f"[DirectionPredictor] Loaded {len(df)} rows, "
                  f"{len(self._feature_cols)} feature columns")

    # ------------------------------------------------------------------
    # Feature window builder
    # ------------------------------------------------------------------

    def _build_window(self, idx: int) -> np.ndarray:
        """Build (1, window_size, n_features) input tensor."""
        window_size = int(self.params['window_size'])
        start = max(0, idx - window_size + 1)
        window = self._data.iloc[start:idx + 1]
        feat_cols = [c for c in self._feature_cols if c in window.columns]
        X = window[feat_cols].values.astype(np.float32)
        if X.shape[0] < window_size:
            pad = np.zeros((window_size - X.shape[0], X.shape[1]),
                           dtype=np.float32)
            X = np.vstack([pad, X])
        return X.reshape(1, window_size, -1)

    def _predict_proba(self, model, X_input: np.ndarray) -> tuple:
        """Run inference, optionally with MC dropout."""
        if self.params['mc_samples'] > 0:
            preds = np.array([
                model(X_input, training=True).numpy()
                for _ in range(self.params['mc_samples'])
            ])
            mean_pred = float(preds.mean())
            std_pred = float(preds.std())
            confidence = max(0.0, 1.0 - 2.0 * std_pred)
        else:
            pred = model.predict(X_input, verbose=0)
            mean_pred = float(np.asarray(pred).flatten()[0])
            confidence = 1.0
        return mean_pred, confidence

    # ------------------------------------------------------------------
    # Entry prediction
    # ------------------------------------------------------------------

    def predict_entry(self, timestamp, tp_pips: float = 0.0,
                      sl_pips: float = 0.0, spread_pips: float = 0.0,
                      commission_per_lot: float = 0.0,
                      slippage_pips: float = 0.0) -> Dict[str, Any]:
        """Predict entry signals using direction_long model.

        P(up) > threshold → buy_entry
        P(up) < (1 - threshold) → sell_entry
        """
        if self._data is None:
            raise RuntimeError("Data not loaded — call load_data first")

        ts = pd.Timestamp(timestamp)
        idx = self._data.index.get_indexer([ts], method='ffill')[0]
        if idx < 0:
            idx = 0

        close_col = self.params['close_column']
        current_price = 0.0
        if close_col in self._data.columns:
            current_price = float(self._data.iloc[idx][close_col])
        bars_remaining = self._bars_to_friday_close(idx)

        threshold = float(self.params['confidence_threshold'])

        if self._long_model is None:
            return {
                "buy_entry_binary": 0.0, "sell_entry_binary": 0.0,
                "bars_remaining": bars_remaining,
                "buy_confidence": 0.0, "sell_confidence": 0.0,
                "timestamp": str(ts), "current_price": current_price,
            }

        X_input = self._build_window(idx)
        p_up, confidence = self._predict_proba(self._long_model, X_input)

        return {
            "buy_entry_binary": 1.0 if p_up >= threshold else 0.0,
            "sell_entry_binary": 1.0 if (1.0 - p_up) >= threshold else 0.0,
            "bars_remaining": bars_remaining,
            "buy_confidence": confidence,
            "sell_confidence": confidence,
            "p_up_long": p_up,
            "timestamp": str(ts),
            "current_price": current_price,
        }

    # ------------------------------------------------------------------
    # Exit prediction
    # ------------------------------------------------------------------

    def predict_exit(self, timestamp, direction: str,
                     tp_price: float, sl_price: float) -> Dict[str, Any]:
        """Predict exit signals using direction_short model.

        For a buy position: P(up over short horizon) < (1-threshold) → exit
        For a sell position: P(up over short horizon) > threshold → exit
        """
        ts = pd.Timestamp(timestamp)

        if self._short_model is None or self._data is None:
            return {
                "exit_binary": 1.0, "exit_confidence": 1.0,
                "timestamp": str(ts), "current_price": 0.0,
            }

        idx = self._data.index.get_indexer([ts], method='ffill')[0]
        if idx < 0:
            idx = 0

        close_col = self.params['close_column']
        current_price = 0.0
        if close_col in self._data.columns:
            current_price = float(self._data.iloc[idx][close_col])

        X_input = self._build_window(idx)
        p_up, confidence = self._predict_proba(self._short_model, X_input)

        threshold = float(self.params['confidence_threshold'])

        # Exit when short-horizon direction opposes the open position
        if direction == 'buy':
            # Exit buy when short-horizon direction is bearish
            should_exit = (1.0 - p_up) >= threshold
        else:
            # Exit sell when short-horizon direction is bullish
            should_exit = p_up >= threshold

        return {
            "exit_binary": 0.0 if should_exit else 1.0,
            "exit_confidence": confidence,
            "p_up_short": p_up,
            "timestamp": str(ts),
            "current_price": current_price,
        }

    # ------------------------------------------------------------------
    # Model info
    # ------------------------------------------------------------------

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "model_name": "direction_predictor",
            "window_size": self.params["window_size"],
            "supported_types": ["entry", "exit"],
            "entry_directions": ["buy", "sell"],
            "exit_directions": ["buy", "sell"],
            "prediction_scope": "directional",
            "required_columns": (self._feature_cols[:10]
                                 if self._feature_cols
                                 else ["OPEN", "HIGH", "LOW", "CLOSE"]),
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


Plugin = DirectionPredictor
