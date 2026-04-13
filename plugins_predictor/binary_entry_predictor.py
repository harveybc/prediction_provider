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
        "use_ideal_buy_exit": False,
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
        """Load a pre-trained Keras model for entry prediction.

        The .keras file is a zip containing model.weights.h5 and config.json.
        Lambda layers with closures (e.g. positional encoding) cannot be
        deserialized directly in Keras 3, so we rebuild the architecture from
        the config inside the zip and load weights separately.
        """
        import tensorflow as tf
        import zipfile
        import tempfile

        if not _os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")

        # 1) Load metadata first (feature_columns, window_size)
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

        # 2) Extract architecture params from the .keras zip config.json
        arch_params = self._extract_arch_params(model_path)

        # 3) Rebuild model architecture using the predictor repo's TFT plugin
        window_size = int(self.params['window_size'])
        n_features = len(self._feature_cols) if self._feature_cols else arch_params.get('n_features', 22)
        self._model = self._build_model_architecture(
            window_size, n_features, arch_params)

        # 4) Load weights from the .keras zip
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(model_path, 'r') as zf:
                zf.extractall(tmpdir)
            weights_path = _os.path.join(tmpdir, 'model.weights.h5')
            if not _os.path.exists(weights_path):
                raise FileNotFoundError(
                    f"No model.weights.h5 inside {model_path}")
            self._model.load_weights(weights_path)

        if not _QUIET:
            print(f"[BinaryEntryPredictor] Loaded model from {model_path} "
                  f"(rebuilt architecture + weights)")

        # Load normalization params if available
        norm_path = self.params.get("normalization_params_path")
        if norm_path and _os.path.exists(norm_path):
            with open(norm_path) as f:
                self._normalization_params = json.load(f)

    @staticmethod
    def _extract_arch_params(keras_path: str) -> dict:
        """Read config.json inside a .keras zip to infer architecture params."""
        import zipfile
        with zipfile.ZipFile(keras_path, 'r') as zf:
            config = json.loads(zf.read('config.json'))
        layers = config.get('config', {}).get('layers', [])
        params: Dict[str, Any] = {}
        units_set = set()
        lstm_count = 0
        has_positional = False
        for layer in layers:
            cls = layer.get('class_name', '')
            cfg = layer.get('config', {})
            if cls == 'Dense' and cfg.get('name', '').startswith('dense'):
                units_set.add(cfg.get('units'))
            elif cls == 'LSTM':
                lstm_count += 1
                units_set.add(cfg.get('units'))
            elif cls == 'MultiHeadAttention':
                params['num_heads'] = cfg.get('num_heads', 2)
            elif cls == 'Dropout':
                params.setdefault('dropout', cfg.get('rate', 0.1))
            elif cls == 'Lambda':
                has_positional = True
                build_cfg = cfg.get('build_config', {})
                input_shape = build_cfg.get('input_shape', [None, 124, 22])
                if input_shape and len(input_shape) == 3:
                    params['n_features'] = input_shape[2]
            elif cls == 'InputLayer':
                shape = cfg.get('batch_shape', [None, 124, 22])
                if shape and len(shape) == 3:
                    params['n_features'] = shape[2]
        # Hidden units = most common Dense unit count (exclude output)
        units_set.discard(1)  # output layer
        if units_set:
            params['hidden_units'] = max(units_set, key=lambda u: sum(
                1 for l in layers
                if l.get('config', {}).get('units') == u))
        params['lstm_layers'] = lstm_count
        params['positional_encoding'] = has_positional
        return params

    @staticmethod
    def _build_model_architecture(window_size: int, n_features: int,
                                   arch: dict):
        """Rebuild TFT binary model architecture (matching predictor repo)."""
        from tensorflow.keras.layers import (
            Input, Dense, Lambda, Add, LSTM,
            LayerNormalization, MultiHeadAttention, Multiply, Dropout,
        )
        from tensorflow.keras.models import Model
        from tensorflow.keras.regularizers import l2

        units = int(arch.get('hidden_units', 64))
        num_heads = int(arch.get('num_heads', 2))
        dropout_rate = float(arch.get('dropout', 0.1))
        lstm_layers = int(arch.get('lstm_layers', 2))
        l2_val = 1e-6
        use_pe = arch.get('positional_encoding', True)

        def _glu(x, u, l2v):
            val = Dense(u, activation=None, kernel_regularizer=l2(l2v))(x)
            gate = Dense(u, activation='sigmoid', kernel_regularizer=l2(l2v))(x)
            return Multiply()([val, gate])

        def _grn(x, u, dr, l2v):
            skip = x
            if x.shape[-1] != u:
                skip = Dense(u, kernel_regularizer=l2(l2v))(x)
            h = Dense(u, activation='elu', kernel_regularizer=l2(l2v))(x)
            h = Dense(u, kernel_regularizer=l2(l2v))(h)
            h = Dropout(dr)(h)
            h = _glu(h, u, l2v)
            h = Add()([skip, h])
            h = LayerNormalization()(h)
            return h

        inputs = Input(shape=(window_size, n_features), name='input_layer')
        if use_pe:
            pe_matrix = np.zeros((1, window_size, n_features), dtype=np.float32)
            for pos in range(window_size):
                for i in range(0, n_features, 2):
                    denom = 10000 ** (i / n_features)
                    pe_matrix[0, pos, i] = np.sin(pos / denom)
                    if i + 1 < n_features:
                        pe_matrix[0, pos, i + 1] = np.cos(pos / denom)
            import tensorflow as _tf
            pe_const = _tf.constant(pe_matrix, dtype=_tf.float32)
            x = Lambda(lambda t, pes=pe_const: t + pes,
                       name='add_positional_encoding')(inputs)
        else:
            x = inputs

        x = _grn(x, units, dropout_rate, l2_val)
        for i in range(lstm_layers):
            x = LSTM(units, return_sequences=True, dropout=dropout_rate,
                     kernel_regularizer=l2(l2_val),
                     name=f'lstm_enc_{i+1}')(x)
            x = _grn(x, units, dropout_rate, l2_val)

        attn_out = MultiHeadAttention(
            num_heads=num_heads, key_dim=units,
            name='self_mha')(x, x)
        h = _grn(attn_out, units, dropout_rate, l2_val)
        h = Add()([x, h])
        h = LayerNormalization()(h)

        # Last timestep
        context = Lambda(lambda t: t[:, -1, :])(h)

        # Binary output head
        head = _grn(context, units, dropout_rate, l2_val)
        output = Dense(1, activation='sigmoid',
                       name='output_horizon_1')(head)

        model = Model(inputs=inputs, outputs=[output],
                      name='BinaryTFT_buy_entry')
        return model

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

        close_col = self.params['close_column']
        if close_col in self._data.columns:
            current_price = float(self._data.iloc[idx][close_col])
        else:
            current_price = 0.0
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
            mean_pred = preds.mean(axis=0).flatten()
            std_pred = preds.std(axis=0).flatten()
            buy_prob = float(mean_pred[0])
            buy_conf = float(max(0.0, 1.0 - 2.0 * std_pred[0]))
        else:
            pred = self._model.predict(X_input, verbose=0)
            buy_prob = float(np.asarray(pred).flatten()[0])
            buy_conf = 1.0

        threshold = float(self.params['confidence_threshold'])
        return {
            "buy_entry_binary": 1.0 if buy_prob >= threshold else 0.0,
            "sell_entry_binary": 1.0 if (1.0 - buy_prob) >= threshold else 0.0,
            "bars_remaining": bars_remaining,
            "buy_confidence": buy_conf,
            "sell_confidence": buy_conf,
            "timestamp": str(ts),
            "current_price": current_price,
        }

    # ------------------------------------------------------------------
    # Exit prediction (stub — delegate to BinaryExitPredictor)
    # ------------------------------------------------------------------

    def predict_exit(self, timestamp, direction: str,
                     tp_price: float, sl_price: float) -> Dict[str, Any]:
        """Return exit prediction.

        When *use_ideal_buy_exit* is True, the actual exit label from the
        dataset is returned (perfect foresight baseline).  Uses
        buy_exit_label for buy direction, sell_exit_label for sell.
        Otherwise falls back to keep-open stub.
        """
        ts = pd.Timestamp(timestamp)

        # Ideal exit: look up the ground-truth label
        use_ideal = self.params.get('use_ideal_buy_exit', False)

        if use_ideal and self._data is not None:
            label_col = None
            if direction == 'buy' and 'buy_exit_label' in self._data.columns:
                label_col = 'buy_exit_label'
            elif direction == 'sell' and 'sell_exit_label' in self._data.columns:
                label_col = 'sell_exit_label'

            if label_col is not None:
                idx = self._data.index.get_indexer([ts], method='ffill')[0]
                if idx < 0:
                    idx = 0
                label = float(self._data.iloc[idx][label_col])
                # label==1 means "TP still reachable" → keep open (exit_binary=1)
                # label==0 means "TP not reachable"   → close     (exit_binary=0)
                exit_bin = 1.0 if label >= 0.5 else 0.0
                return {
                    "exit_binary": exit_bin,
                    "exit_confidence": 1.0,
                    "timestamp": str(ts),
                    "current_price": 0.0,
                }

        # Default stub: keep open
        return {
            "exit_binary": 1.0, "exit_confidence": 1.0,
            "timestamp": str(ts), "current_price": 0.0,
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
