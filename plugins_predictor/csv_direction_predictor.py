#!/usr/bin/env python3
"""
CSV Direction Predictor Plugin (Pre-computed Predictions)

Loads pre-computed prediction CSV files (from the predictor repo's
inference mode) and serves them via the sync_core entry/exit API.

This avoids needing to replicate the predictor's feature engineering
pipeline (window stats, temporal features, etc.) inside PP.

CSV format (one per model):
    DATE_TIME, True_Label_H1, Probability_H1, Predicted_Label_H1

Config keys:
    long_predictions_csv  (str)   – path to direction_long predictions CSV
    short_predictions_csv (str)   – path to direction_short predictions CSV
    csv_file              (str)   – path to OHLC base data CSV (for prices)
    confidence_threshold  (float) – min prob to emit signal (default 0.55)
"""

import os as _os
_QUIET = _os.environ.get('PREDICTION_PROVIDER_QUIET', '0') == '1'

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional


class CsvDirectionPredictor:
    """Serves pre-computed direction predictions from CSV files."""

    plugin_params = {
        "long_predictions_csv": None,
        "short_predictions_csv": None,
        "csv_file": None,
        "confidence_threshold": 0.55,
        "close_column": "CLOSE",
        "datetime_column": "DATE_TIME",
        "pip_cost": 0.00001,
        "prediction_horizon": 120,
        "friday_close_hour": 20,
    }

    plugin_debug_vars = [
        "long_predictions_csv", "short_predictions_csv",
        "csv_file", "confidence_threshold",
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.params = self.plugin_params.copy()
        if config:
            for k, v in config.items():
                if k in self.params:
                    self.params[k] = v

        self._long_preds: Optional[pd.DataFrame] = None
        self._short_preds: Optional[pd.DataFrame] = None
        self._ohlc: Optional[pd.DataFrame] = None

        if self.params["long_predictions_csv"]:
            self._long_preds = self._load_predictions(
                self.params["long_predictions_csv"], "long"
            )
        if self.params["short_predictions_csv"]:
            self._short_preds = self._load_predictions(
                self.params["short_predictions_csv"], "short"
            )
        if self.params["csv_file"]:
            self._load_ohlc(self.params["csv_file"])

    def set_params(self, **kwargs):
        for k, v in kwargs.items():
            if k in self.params:
                self.params[k] = v

    def get_debug_info(self) -> Dict[str, Any]:
        info = {k: self.params.get(k) for k in self.plugin_debug_vars}
        info["long_preds_loaded"] = self._long_preds is not None
        info["short_preds_loaded"] = self._short_preds is not None
        info["ohlc_loaded"] = self._ohlc is not None
        if self._long_preds is not None:
            info["long_preds_count"] = len(self._long_preds)
        if self._short_preds is not None:
            info["short_preds_count"] = len(self._short_preds)
        return info

    def _load_predictions(self, csv_path: str, label: str) -> pd.DataFrame:
        if not _os.path.exists(csv_path):
            raise FileNotFoundError(f"Predictions CSV not found: {csv_path}")
        df = pd.read_csv(csv_path, parse_dates=["DATE_TIME"])
        df.set_index("DATE_TIME", inplace=True)
        df.sort_index(inplace=True)
        if not _QUIET:
            print(f"[CsvDirectionPredictor:{label}] Loaded {len(df)} predictions "
                  f"from {csv_path}")
        return df

    def _load_ohlc(self, csv_path: str):
        if not _os.path.exists(csv_path):
            if not _QUIET:
                print(f"[CsvDirectionPredictor] OHLC file not found: {csv_path}")
            return
        df = pd.read_csv(csv_path)
        dt_col = self.params["datetime_column"]
        if dt_col in df.columns:
            df[dt_col] = pd.to_datetime(df[dt_col])
            df.set_index(dt_col, inplace=True)
        df.sort_index(inplace=True)
        self._ohlc = df
        if not _QUIET:
            print(f"[CsvDirectionPredictor] Loaded {len(df)} OHLC rows")

    def _lookup_prediction(self, preds_df: pd.DataFrame,
                           timestamp) -> Optional[float]:
        """Look up probability for nearest timestamp."""
        ts = pd.Timestamp(timestamp)
        if ts in preds_df.index:
            return float(preds_df.loc[ts, "Probability_H1"])
        # Try nearest match (within 2 hours)
        idx = preds_df.index.get_indexer([ts], method="nearest")[0]
        if idx >= 0 and idx < len(preds_df):
            nearest_ts = preds_df.index[idx]
            if abs((nearest_ts - ts).total_seconds()) <= 7200:
                return float(preds_df.iloc[idx]["Probability_H1"])
        return None

    def _get_current_price(self, timestamp) -> float:
        if self._ohlc is None:
            return 0.0
        ts = pd.Timestamp(timestamp)
        close_col = self.params["close_column"]
        if close_col not in self._ohlc.columns:
            return 0.0
        idx = self._ohlc.index.get_indexer([ts], method="ffill")[0]
        if idx >= 0:
            return float(self._ohlc.iloc[idx][close_col])
        return 0.0

    def _bars_to_friday_close(self, timestamp) -> int:
        ts = pd.Timestamp(timestamp)
        friday_hour = int(self.params["friday_close_hour"])
        if hasattr(ts, "weekday") and ts.weekday() == 4 and ts.hour >= friday_hour:
            return 0
        # Estimate bars remaining
        days_to_friday = (4 - ts.weekday()) % 7
        hours_remaining = days_to_friday * 24 + (friday_hour - ts.hour)
        return max(0, hours_remaining // 4)  # 4h bars

    # ------------------------------------------------------------------
    # Entry prediction
    # ------------------------------------------------------------------

    def predict_entry(self, timestamp, tp_pips: float = 0.0,
                      sl_pips: float = 0.0, spread_pips: float = 0.0,
                      commission_per_lot: float = 0.0,
                      slippage_pips: float = 0.0) -> Dict[str, Any]:
        """Predict entry signals using pre-computed long predictions."""
        ts = pd.Timestamp(timestamp)
        current_price = self._get_current_price(ts)
        bars_remaining = self._bars_to_friday_close(ts)
        threshold = float(self.params["confidence_threshold"])

        if self._long_preds is None:
            return {
                "buy_entry_binary": 0.0, "sell_entry_binary": 0.0,
                "bars_remaining": bars_remaining,
                "buy_confidence": 0.0, "sell_confidence": 0.0,
                "timestamp": str(ts), "current_price": current_price,
            }

        p_up = self._lookup_prediction(self._long_preds, ts)
        if p_up is None:
            return {
                "buy_entry_binary": 0.0, "sell_entry_binary": 0.0,
                "bars_remaining": bars_remaining,
                "buy_confidence": 0.0, "sell_confidence": 0.0,
                "timestamp": str(ts), "current_price": current_price,
            }

        return {
            "buy_entry_binary": 1.0 if p_up >= threshold else 0.0,
            "sell_entry_binary": 1.0 if (1.0 - p_up) >= threshold else 0.0,
            "bars_remaining": bars_remaining,
            "buy_confidence": 1.0,
            "sell_confidence": 1.0,
            "p_up_long": p_up,
            "timestamp": str(ts),
            "current_price": current_price,
        }

    # ------------------------------------------------------------------
    # Exit prediction
    # ------------------------------------------------------------------

    def predict_exit(self, timestamp, direction: str,
                     tp_price: float, sl_price: float) -> Dict[str, Any]:
        """Predict exit signals using pre-computed short predictions."""
        ts = pd.Timestamp(timestamp)
        current_price = self._get_current_price(ts)

        if self._short_preds is None:
            return {
                "exit_binary": 1.0, "exit_confidence": 1.0,
                "timestamp": str(ts), "current_price": current_price,
            }

        p_up = self._lookup_prediction(self._short_preds, ts)
        if p_up is None:
            return {
                "exit_binary": 1.0, "exit_confidence": 1.0,
                "timestamp": str(ts), "current_price": current_price,
            }

        threshold = float(self.params["confidence_threshold"])

        # SHORT model: Probability_H1 = p(downward movement)
        p_down = p_up  # rename for clarity
        if direction == "buy":
            # Exit buy when SHORT model says price likely going DOWN
            should_exit = p_down >= threshold
        else:
            # Exit sell when SHORT model says price likely going UP
            should_exit = (1.0 - p_down) >= threshold

        return {
            "exit_binary": 0.0 if should_exit else 1.0,
            "exit_confidence": 1.0,
            "p_up_short": p_up,
            "timestamp": str(ts),
            "current_price": current_price,
        }

    # ------------------------------------------------------------------
    # Model info
    # ------------------------------------------------------------------

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "model_name": "csv_direction_predictor",
            "window_size": 0,
            "supported_types": ["entry", "exit"],
            "entry_directions": ["buy", "sell"],
            "exit_directions": ["buy", "sell"],
            "prediction_scope": "directional",
            "required_columns": [],
            "accepts_ohlc_window": False,
        }


Plugin = CsvDirectionPredictor
