#!/usr/bin/env python3
"""
Direction Ideal Oracle Predictor Plugin

A truly ideal oracle that uses future price data (look-ahead) to provide
*perfect* entry/exit signals by scanning the actual price path:

  - **Entry**: Scans future bars for BOTH directions (buy and sell), checking
    whether the ATR-derived TP is hit before the SL.  Returns buy=1 only
    when the buy TP is actually reached before the buy SL (and vice-versa).
  - **Exit**:  Scans remaining bars to check if the open position's TP will
    still be hit before its SL.  Returns exit_binary=1 (keep) or 0 (close).

This represents the *true theoretical ceiling* of the direction_atr strategy:
perfect knowledge of which trades will be profitable.

Config keys:
    csv_file              (str)   – path to OHLC CSV
    atr_period            (int)   – ATR lookback period
    noise_std             (float) – Gaussian noise σ on latent score (0.0 = perfect)
    noise_seed            (int)   – random seed for noise
    pip_cost              (float) – one pip in price units
    friday_close_hour     (int)   – hour at which trading week ends
"""

import os as _os
_QUIET = _os.environ.get('PREDICTION_PROVIDER_QUIET', '0') == '1'

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional


class DirectionIdealOracle:
    """Oracle that scans future price path to determine if TP hits before SL."""

    plugin_params = {
        "csv_file": None,
        "atr_period": 14,
        "noise_std": 0.0,
        "noise_seed": 42,
        "close_column": "CLOSE",
        "high_column": "HIGH",
        "low_column": "LOW",
        "datetime_column": "DATE_TIME",
        "pip_cost": 0.00001,
        "prediction_horizon": 120,
        "friday_close_hour": 20,
        "window_size": 0,
    }

    plugin_debug_vars = [
        "csv_file", "atr_period",
        "noise_std", "pip_cost", "friday_close_hour",
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.params = self.plugin_params.copy()
        if config:
            for k, v in config.items():
                if k in self.params:
                    self.params[k] = v

        self._data: Optional[pd.DataFrame] = None
        self._atr: Optional[np.ndarray] = None
        self._rng: Optional[np.random.Generator] = None
        self._loaded = False

        # F1 tracking counters (noisy prediction vs true oracle)
        self._tp = 0   # true positive
        self._fp = 0   # false positive
        self._tn = 0   # true negative
        self._fn = 0   # false negative

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
        return {k: self.params.get(k) for k in self.plugin_debug_vars}

    # ------------------------------------------------------------------
    # Data loading + ATR pre-computation
    # ------------------------------------------------------------------

    def load_data(self, csv_file: str):
        """Load OHLC data and pre-compute ATR."""
        if not _os.path.exists(csv_file):
            raise FileNotFoundError(f"CSV file not found: {csv_file}")

        dt_col = self.params["datetime_column"]
        df = pd.read_csv(csv_file)
        if dt_col in df.columns:
            df[dt_col] = pd.to_datetime(df[dt_col])
            df.set_index(dt_col, inplace=True)
        df.sort_index(inplace=True)
        self._data = df
        self._rng = np.random.default_rng(self.params["noise_seed"])

        # Pre-compute ATR
        self._compute_atr()
        self._loaded = True

        if not _QUIET:
            print(f"[DirectionIdealOracle] Loaded {len(df)} bars, "
                  f"ATR period={self.params['atr_period']}")

    def _compute_atr(self):
        """Compute ATR (Average True Range) for all bars."""
        high = self._data[self.params["high_column"]].values.astype(float)
        low = self._data[self.params["low_column"]].values.astype(float)
        close = self._data[self.params["close_column"]].values.astype(float)
        n = len(self._data)
        period = int(self.params["atr_period"])

        # True Range
        tr = np.zeros(n)
        tr[0] = high[0] - low[0]
        for i in range(1, n):
            tr[i] = max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1]),
            )

        # EMA-based ATR (Wilder smoothing)
        atr = np.zeros(n)
        atr[:period] = np.nan
        if period <= n:
            atr[period - 1] = np.mean(tr[:period])
            alpha = 1.0 / period
            for i in range(period, n):
                atr[i] = atr[i - 1] * (1 - alpha) + tr[i] * alpha

        self._atr = atr

    @property
    def data_loaded(self) -> bool:
        return self._loaded

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _bars_to_friday_close(self, idx: int) -> int:
        friday_hour = self.params["friday_close_hour"]
        n = len(self._data)
        count = 0
        for i in range(idx + 1, n):
            dt = self._data.index[i]
            count += 1
            if dt.weekday() == 4 and dt.hour >= friday_hour:
                return count
            if dt.weekday() == 0 and i > idx + 1:
                return count
        return max(count, self.params["prediction_horizon"])

    def _scan_tp_sl(self, idx: int, tp_price: float, sl_price: float,
                    horizon: int, direction: str) -> float:
        """Scan future bars: does TP get hit before SL?

        For buy:  SL hit when LOW  <= sl_price,  TP hit when CLOSE >= tp_price
        For sell: SL hit when HIGH >= sl_price,  TP hit when CLOSE <= tp_price

        Returns 1.0 if TP hit first, 0.0 if SL hit first or neither hit.
        """
        high_col = self.params["high_column"]
        low_col = self.params["low_column"]
        close_col = self.params["close_column"]
        n = len(self._data)

        for i in range(idx + 1, min(idx + 1 + horizon, n)):
            bar_high = float(self._data.iloc[i][high_col])
            bar_low = float(self._data.iloc[i][low_col])
            bar_close = float(self._data.iloc[i][close_col])

            if direction == "buy":
                if bar_low <= sl_price:
                    return 0.0   # SL hit first
                if bar_close >= tp_price:
                    return 1.0   # TP hit
            else:  # sell
                if bar_high >= sl_price:
                    return 0.0   # SL hit first
                if bar_close <= tp_price:
                    return 1.0   # TP hit

        return 0.0  # neither hit within horizon

    def _apply_noise(self, true_signal: float) -> float:
        """Apply Gaussian noise to the latent score and re-threshold.

        true_signal is 0.0 or 1.0.  We add N(0, noise_std) and threshold
        at 0.5.  This smoothly degrades F1 as noise_std increases.
        """
        sigma = self.params["noise_std"]
        if sigma > 0:
            noisy = true_signal + self._rng.normal(0, sigma)
            pred = 1.0 if noisy > 0.5 else 0.0
        else:
            pred = true_signal

        # Track confusion matrix
        t = int(true_signal > 0.5)
        p = int(pred > 0.5)
        if t == 1 and p == 1:
            self._tp += 1
        elif t == 0 and p == 1:
            self._fp += 1
        elif t == 0 and p == 0:
            self._tn += 1
        else:
            self._fn += 1

        return pred

    def _get_atr_at(self, idx: int) -> float:
        """Return ATR at bar idx, or fallback if not yet computed."""
        if self._atr is not None and idx < len(self._atr):
            val = self._atr[idx]
            if not np.isnan(val) and val > 0:
                return float(val)
        # Fallback: simple range of recent bars
        n = min(14, idx + 1)
        if n < 1:
            return 0.001
        high = self._data[self.params["high_column"]].values
        low = self._data[self.params["low_column"]].values
        recent_range = np.mean(high[idx - n + 1:idx + 1] - low[idx - n + 1:idx + 1])
        return max(float(recent_range), 0.0001)

    # ------------------------------------------------------------------
    # Entry prediction — scan TP/SL path for both directions
    # ------------------------------------------------------------------

    def predict_entry(self, timestamp, tp_pips: float = 0.0,
                      sl_pips: float = 0.0, spread_pips: float = 0.0,
                      commission_per_lot: float = 0.0,
                      slippage_pips: float = 0.0) -> Dict[str, Any]:
        """
        Truly ideal entry oracle: scans the actual price path to determine
        whether the ATR-based TP will be hit before the SL for each direction.

        The strategy sends tp_pips/sl_pips (ATR-derived). This oracle uses
        those exact levels to scan future bars.
        """
        if self._data is None:
            raise RuntimeError("Data not loaded – call load_data first")

        ts = pd.Timestamp(timestamp)
        idx = self._data.index.get_indexer([ts], method="nearest")[0]
        close_col = self.params["close_column"]
        pip = self.params["pip_cost"]
        current_price = float(self._data.iloc[idx][close_col])
        horizon = self._bars_to_friday_close(idx)

        # Convert pips to price distances
        tp_dist = tp_pips * pip
        sl_dist = sl_pips * pip

        # Cost adjustment: widen TP by spread + slippage + commission
        cost_pips = spread_pips + slippage_pips
        if commission_per_lot > 0:
            cost_pips += (commission_per_lot / (100000.0 * pip)) * 2
        cost_dist = cost_pips * pip

        # Buy TP/SL
        buy_tp = current_price + tp_dist + cost_dist
        buy_sl = current_price - sl_dist
        # Sell TP/SL
        sell_tp = current_price - tp_dist - cost_dist
        sell_sl = current_price + sl_dist

        # Scan price path for each direction
        buy_true = self._scan_tp_sl(idx, buy_tp, buy_sl, horizon, "buy")
        sell_true = self._scan_tp_sl(idx, sell_tp, sell_sl, horizon, "sell")

        buy_binary = self._apply_noise(buy_true)
        sell_binary = self._apply_noise(sell_true)

        current_atr = self._get_atr_at(idx)

        return {
            "buy_entry_binary": buy_binary,
            "sell_entry_binary": sell_binary,
            "bars_remaining": horizon,
            "buy_confidence": 1.0,
            "sell_confidence": 1.0,
            "atr": current_atr,
            "timestamp": self._data.index[idx].isoformat(),
            "current_price": current_price,
        }

    # ------------------------------------------------------------------
    # Exit prediction — scan remaining path for open position
    # ------------------------------------------------------------------

    def predict_exit(self, timestamp, direction: str,
                     tp_price: float, sl_price: float) -> Dict[str, Any]:
        """
        Truly ideal exit oracle: scans remaining bars to check if the
        open position's TP will still be hit before its SL.

        exit_binary = 1 → TP still expected (keep open)
        exit_binary = 0 → TP unlikely / SL expected (close early)
        """
        if self._data is None:
            raise RuntimeError("Data not loaded – call load_data first")

        ts = pd.Timestamp(timestamp)
        idx = self._data.index.get_indexer([ts], method="nearest")[0]
        close_col = self.params["close_column"]
        current_price = float(self._data.iloc[idx][close_col])

        horizon = self._bars_to_friday_close(idx)

        # Scan from current bar: does TP get hit before SL?
        true_exit = self._scan_tp_sl(idx, tp_price, sl_price, horizon, direction)
        exit_binary = self._apply_noise(true_exit)

        return {
            "exit_binary": exit_binary,
            "exit_confidence": 1.0,
            "timestamp": self._data.index[idx].isoformat(),
            "current_price": current_price,
        }

    # ------------------------------------------------------------------
    # Model info
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def reset_metrics(self):
        """Reset confusion matrix counters."""
        self._tp = 0
        self._fp = 0
        self._tn = 0
        self._fn = 0
        # Re-seed RNG for reproducibility across noise sweeps
        self._rng = np.random.default_rng(self.params["noise_seed"])

    def get_metrics(self) -> Dict[str, Any]:
        """Return precision, recall, F1 of noisy predictions vs true oracle."""
        tp, fp, tn, fn = self._tp, self._fp, self._tn, self._fn
        total = tp + fp + tn + fn
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) > 0 else 0.0)
        accuracy = (tp + tn) / total if total > 0 else 0.0
        return {
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "total_predictions": total,
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
            "accuracy": round(accuracy, 6),
            "noise_std": self.params["noise_std"],
        }

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "model_name": "direction_ideal_oracle",
            "window_size": self.params["window_size"],
            "supported_types": ["entry", "exit"],
            "entry_directions": ["buy", "sell"],
            "exit_directions": ["buy", "sell"],
            "prediction_scope": "path_scanning",
            "noise_std": self.params["noise_std"],
            "atr_period": self.params["atr_period"],
            "required_columns": ["OPEN", "HIGH", "LOW", "CLOSE"],
            "accepts_ohlc_window": False,
        }


Plugin = DirectionIdealOracle
