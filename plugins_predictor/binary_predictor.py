#!/usr/bin/env python3
"""
Binary Predictor Plugin (combined entry + exit, inference only)

Wraps BinaryEntryPredictor and BinaryExitPredictor so sync_core can use
a single plugin for both predict_entry() and predict_exit() calls.

Both sub-predictors load pre-trained Keras models produced by the
predictor repo.  No model architecture or training is defined here.

Config keys:
    entry_model_path    – path to entry model (.keras)
    exit_model_path     – path to exit model (.keras)
    csv_file            – OHLC+features CSV for data lookback
    entry_window_size   – window for entry model (default 64)
    exit_window_size    – window for exit model (default 32)
    mc_samples          – MC dropout samples (0=off)
    confidence_threshold – min prob to emit signal (0.5)
"""

import os as _os
_QUIET = _os.environ.get('PREDICTION_PROVIDER_QUIET', '0') == '1'

from typing import Dict, Any, Optional

from plugins_predictor.binary_entry_predictor import BinaryEntryPredictor
from plugins_predictor.binary_exit_predictor import BinaryExitPredictor


class BinaryPredictor:
    """Combined entry + exit binary predictor for sync_core (inference only)."""

    plugin_params = {
        "entry_model_path": None,
        "exit_model_path": None,
        "csv_file": None,
        "entry_window_size": 64,
        "exit_window_size": 32,
        "mc_samples": 0,
        "close_column": "CLOSE",
        "high_column": "HIGH",
        "low_column": "LOW",
        "datetime_column": "DATE_TIME",
        "pip_cost": 0.00001,
        "prediction_horizon": 120,
        "friday_close_hour": 20,
        "confidence_threshold": 0.5,
        "normalization_params_path": None,
    }

    plugin_debug_vars = [
        "entry_model_path", "exit_model_path", "csv_file",
        "entry_window_size", "exit_window_size", "mc_samples",
        "confidence_threshold",
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.params = self.plugin_params.copy()
        if config:
            for k, v in config.items():
                if k in self.params:
                    self.params[k] = v

        # Build sub-configs
        shared = {k: self.params[k] for k in [
            "csv_file", "mc_samples", "close_column", "high_column",
            "low_column", "datetime_column", "pip_cost",
            "prediction_horizon", "friday_close_hour",
            "confidence_threshold", "normalization_params_path",
        ]}

        entry_config = {**shared,
                        "model_path": self.params["entry_model_path"],
                        "window_size": self.params["entry_window_size"]}
        exit_config = {**shared,
                       "model_path": self.params["exit_model_path"],
                       "window_size": self.params["exit_window_size"]}

        self._entry = BinaryEntryPredictor(entry_config)
        self._exit = BinaryExitPredictor(exit_config)

    def set_params(self, **kwargs):
        for k, v in kwargs.items():
            if k in self.params:
                self.params[k] = v

    def get_debug_info(self) -> Dict[str, Any]:
        info = {k: self.params.get(k) for k in self.plugin_debug_vars}
        info["entry_debug"] = self._entry.get_debug_info()
        info["exit_debug"] = self._exit.get_debug_info()
        return info

    def load_data(self, csv_file: str):
        self._entry.load_data(csv_file)
        self._exit.load_data(csv_file)

    def predict_entry(self, timestamp, tp_pips=0.0, sl_pips=0.0,
                      spread_pips=0.0, commission_per_lot=0.0,
                      slippage_pips=0.0) -> Dict[str, Any]:
        return self._entry.predict_entry(
            timestamp, tp_pips, sl_pips, spread_pips,
            commission_per_lot, slippage_pips)

    def predict_exit(self, timestamp, direction: str,
                     tp_price: float, sl_price: float) -> Dict[str, Any]:
        return self._exit.predict_exit(timestamp, direction, tp_price, sl_price)

    def get_model_info(self) -> Dict[str, Any]:
        entry_info = self._entry.get_model_info()
        exit_info = self._exit.get_model_info()
        return {
            "model_name": "binary_predictor",
            "window_size": max(entry_info.get("window_size", 64),
                               exit_info.get("window_size", 32)),
            "entry_window_size": entry_info.get("window_size", 64),
            "exit_window_size": exit_info.get("window_size", 32),
            "supported_types": ["entry", "exit"],
            "entry_directions": ["buy", "sell"],
            "exit_directions": ["buy", "sell"],
            "prediction_scope": "weekly_and_short_term",
            "required_columns": entry_info.get("required_columns", []),
            "accepts_ohlc_window": True,
        }


Plugin = BinaryPredictor
