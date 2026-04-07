#!/usr/bin/env python3
"""
Binary Ideal Oracle Predictor Plugin

An oracle predictor that scans future price data to determine whether a
take-profit (TP) level is reached before a stop-loss (SL) level.  Returns
binary signals compatible with the heuristic-strategy
``plugin_api_predictions`` plugin.

Supports two prediction types:
  - **Entry**: given tp/sl in pips, checks both buy and sell directions over
    the remaining bars until Friday close (weekly scope).
  - **Exit**: given absolute tp/sl price levels and the direction of an
    already-open order, checks whether TP is still expected to be hit before
    SL from the current bar.

The oracle uses actual future prices (look-ahead) — it represents the *ideal*
binary predictor.  ``noise_probability`` flips answers to simulate imperfect
accuracy (e.g. 0.1 → 90 % accurate oracle).

Config keys:
    csv_file            (str)   – path to OHLC CSV with DATE_TIME, CLOSE, HIGH, LOW
    noise_probability   (float) – probability of flipping the oracle answer (default 0.0)
    noise_seed          (int)   – random seed for reproducibility  (default 42)
    close_column        (str)   – close-price column name (default 'CLOSE')
    high_column         (str)   – high-price column name  (default 'HIGH')
    low_column          (str)   – low-price column name   (default 'LOW')
    datetime_column     (str)   – datetime column name    (default 'DATE_TIME')
    pip_cost            (float) – one pip in price units   (default 0.00001)
    prediction_horizon  (int)   – fallback horizon in bars (default 30)
    friday_close_hour   (int)   – hour at which trading week ends (default 20)
    window_size         (int)   – advertised input window  (default 0, oracle needs none)
"""

import os as _os
_QUIET = _os.environ.get('PREDICTION_PROVIDER_QUIET', '0') == '1'

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional


class BinaryIdealOracle:
    """
    Oracle predictor that checks whether TP is hit before SL in future data.

    ``predict_entry()`` — answers "should I open a buy / sell?"
    ``predict_exit()``  — answers "should I keep my open order?"
    """

    plugin_params = {
        "csv_file": None,
        "noise_probability": 0.0,
        "noise_seed": 42,
        "close_column": "CLOSE",
        "high_column": "HIGH",
        "low_column": "LOW",
        "datetime_column": "DATE_TIME",
        "pip_cost": 0.00001,
        "prediction_horizon": 30,
        "friday_close_hour": 20,
        "window_size": 0,
        "spread_cost_pips": 5.0,  # spread(2) + slippage(1) + commission(~1) + entry-gap buffer(1)
    }

    plugin_debug_vars = [
        "csv_file", "noise_probability", "noise_seed", "pip_cost",
        "prediction_horizon", "friday_close_hour", "window_size",
        "spread_cost_pips",
    ]

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
    # Helpers
    # ------------------------------------------------------------------

    def _bars_to_friday_close(self, idx: int) -> int:
        """Return the number of bars from *idx* to Friday close (inclusive).

        If the data has gaps (weekends), this counts only actual bars present
        in the dataset.  Falls back to ``prediction_horizon`` if the scan
        exceeds the available data.
        """
        friday_hour = self.params["friday_close_hour"]
        n = len(self._data)
        count = 0
        for i in range(idx + 1, n):
            dt = self._data.index[i]
            count += 1
            # Friday at or past the close hour → stop
            if dt.weekday() == 4 and dt.hour >= friday_hour:
                return count
            # If we jump to a Monday → the week already closed
            if dt.weekday() == 0 and i > idx + 1:
                return count
        # Ran out of data — use fallback
        return max(count, self.params["prediction_horizon"])

    def _scan_tp_sl(self, idx: int, tp_price: float, sl_price: float,
                    horizon: int, direction: str) -> float:
        """
        Scan future bars from *idx+1* to *idx+horizon*.

        For a **buy** trade:
          - TP hit when CLOSE >= tp_price  → return 1.0  (close-based TP)
          - SL hit when LOW   <= sl_price  → return 0.0  (intra-bar SL)

        For a **sell** trade (mirror):
          - TP hit when CLOSE <= tp_price  → return 1.0  (close-based TP)
          - SL hit when HIGH  >= sl_price  → return 0.0  (intra-bar SL)

        Using CLOSE for TP ensures that the strategy (which exits via
        ``self.close()`` with CoC at close price) fills at a price >= TP.
        SL still uses intra-bar HIGH/LOW to catch worst-case stop-outs.

        If neither level is reached within the horizon → return 0.0.
        """
        high_col = self.params["high_column"]
        low_col = self.params["low_column"]
        close_col = self.params["close_column"]
        n = len(self._data)

        for step in range(1, horizon + 1):
            fi = idx + step
            if fi >= n:
                break

            bar_high = float(self._data.iloc[fi][high_col])
            bar_low = float(self._data.iloc[fi][low_col])
            bar_close = float(self._data.iloc[fi][close_col])

            if direction == "buy":
                if bar_low <= sl_price:
                    return 0.0
                if bar_close >= tp_price:
                    return 1.0
            else:  # sell
                if bar_high >= sl_price:
                    return 0.0
                if bar_close <= tp_price:
                    return 1.0

        return 0.0

    def _maybe_flip(self, value: float) -> float:
        """Flip the binary value with probability ``noise_probability``."""
        p = self.params["noise_probability"]
        if p > 0 and self._rng.random() < p:
            return 1.0 - value
        return value

    # ------------------------------------------------------------------
    # Entry prediction
    # ------------------------------------------------------------------

    def predict_entry(self, timestamp, tp_pips: float, sl_pips: float,
                      spread_pips: float = 0.0, commission_per_lot: float = 0.0,
                      slippage_pips: float = 0.0) -> Dict[str, Any]:
        """
        Entry prediction — "should I open a buy / sell order?"

        Computes TP/SL absolute levels from the current price for BOTH
        directions.  Scans future bars until Friday close.

        When ``spread_pips``, ``commission_per_lot``, or ``slippage_pips`` are
        provided (> 0), the oracle computes the exact cost in pips and widens
        TP by that amount.  Otherwise falls back to the configured
        ``spread_cost_pips`` default.

        Returns
        -------
        dict with keys:
            buy_entry_binary   – 1.0 if buy TP hit before buy SL, else 0.0
            sell_entry_binary  – 1.0 if sell TP hit before sell SL, else 0.0
            timestamp          – ISO string of matched bar
            current_price      – price at the reference bar
        """
        if self._data is None:
            raise RuntimeError("Data not loaded – call load_data first")

        ts = pd.Timestamp(timestamp)
        idx = self._data.index.get_indexer([ts], method="nearest")[0]
        pip_cost = self.params["pip_cost"]
        close_col = self.params["close_column"]
        current_price = float(self._data.iloc[idx][close_col])

        tp_pips = tp_pips if tp_pips > 0 else 5.0
        sl_pips = sl_pips if sl_pips > 0 else 10.0

        horizon = self._bars_to_friday_close(idx)

        # Compute cost buffer in pips — use received costs if provided,
        # otherwise fall back to the configured default.
        if spread_pips > 0 or commission_per_lot > 0 or slippage_pips > 0:
            # Commission per lot ($7 / 100K) → pips:  $7 / (100000 * 0.00001) = 7
            # That's per standard lot. Per pip_cost unit it's:
            # commission_pips = commission_per_lot / (100000 * pip_cost)
            commission_pips = commission_per_lot / (100000 * pip_cost) if pip_cost > 0 else 0
            # Round-trip costs: spread + slippage + commission (×2 for entry+exit)
            cost_pips = spread_pips + slippage_pips + commission_pips * 2
        else:
            cost_pips = self.params["spread_cost_pips"]

        # Buy direction — TP must be higher to cover costs
        buy_tp = current_price + (tp_pips + cost_pips) * pip_cost
        buy_sl = current_price - sl_pips * pip_cost
        buy_binary = self._maybe_flip(
            self._scan_tp_sl(idx, buy_tp, buy_sl, horizon, "buy")
        )

        # Sell direction — TP must be lower to cover costs
        sell_tp = current_price - (tp_pips + cost_pips) * pip_cost
        sell_sl = current_price + sl_pips * pip_cost
        sell_binary = self._maybe_flip(
            self._scan_tp_sl(idx, sell_tp, sell_sl, horizon, "sell")
        )

        return {
            "buy_entry_binary": buy_binary,
            "sell_entry_binary": sell_binary,
            "bars_remaining": horizon,
            "timestamp": self._data.index[idx].isoformat(),
            "current_price": current_price,
        }

    # ------------------------------------------------------------------
    # Exit prediction
    # ------------------------------------------------------------------

    def predict_exit(self, timestamp, direction: str,
                     tp_price: float, sl_price: float) -> Dict[str, Any]:
        """
        Exit prediction — "should I keep my open order or close early?"

        Receives ABSOLUTE tp/sl price levels and the direction of the open
        order.  Scans future bars until Friday close.

        Returns
        -------
        dict with keys:
            exit_binary   – 1.0 if TP still expected to be hit (keep open),
                            0.0 if SL expected first or horizon exhausted (close early)
            timestamp     – ISO string of matched bar
            current_price – price at the reference bar
        """
        if self._data is None:
            raise RuntimeError("Data not loaded – call load_data first")

        ts = pd.Timestamp(timestamp)
        idx = self._data.index.get_indexer([ts], method="nearest")[0]
        close_col = self.params["close_column"]
        current_price = float(self._data.iloc[idx][close_col])

        horizon = self._bars_to_friday_close(idx)

        exit_binary = self._maybe_flip(
            self._scan_tp_sl(idx, tp_price, sl_price, horizon, direction)
        )

        return {
            "exit_binary": exit_binary,
            "timestamp": self._data.index[idx].isoformat(),
            "current_price": current_price,
        }

    # ------------------------------------------------------------------
    # Model info
    # ------------------------------------------------------------------

    def get_model_info(self) -> Dict[str, Any]:
        """Return metadata about this predictor for the /model/info endpoint."""
        return {
            "model_name": "binary_ideal_oracle",
            "window_size": self.params["window_size"],
            "supported_types": ["entry", "exit"],
            "entry_directions": ["buy", "sell"],
            "exit_directions": ["buy", "sell"],
            "prediction_scope": "weekly",
            "noise_probability": self.params["noise_probability"],
            "required_columns": ["OPEN", "HIGH", "LOW", "CLOSE"],
            "accepts_ohlc_window": False,
        }

    # ------------------------------------------------------------------
    # Legacy / compatibility
    # ------------------------------------------------------------------

    def predict_at(self, timestamp, tp: float = 0.0, sl: float = 0.0,
                   horizon: int = None, **kwargs) -> Dict[str, Any]:
        """Legacy compatibility — delegates to predict_entry."""
        return self.predict_entry(timestamp, tp_pips=tp, sl_pips=sl)

    def predict(self, input_data: Any = None, **kwargs) -> Dict[str, Any]:
        """Compatibility method for the prediction provider pipeline."""
        tp = kwargs.get("tp", 0.0)
        sl = kwargs.get("sl", 0.0)

        if isinstance(input_data, dict):
            ts = input_data.get("timestamp")
            tp = input_data.get("tp", tp)
            sl = input_data.get("sl", sl)
        elif isinstance(input_data, (str, pd.Timestamp)):
            ts = input_data
        else:
            ts = self._data.index[0] if self._data is not None else None

        if ts is None:
            raise ValueError("No timestamp provided and no data loaded")

        result = self.predict_entry(ts, tp_pips=tp, sl_pips=sl)

        return {
            "buy_entry_binary": result["buy_entry_binary"],
            "sell_entry_binary": result["sell_entry_binary"],
            "timestamp": result["timestamp"],
            "current_price": result["current_price"],
            "model_name": "binary_ideal_oracle",
            "noise_probability": self.params["noise_probability"],
        }
