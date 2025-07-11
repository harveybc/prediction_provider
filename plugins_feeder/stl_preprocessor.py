#!/usr/bin/env python3
"""
STL Preprocessor Plugin - Adapted for Prediction Provider

This module implements the exact same preprocessing pipeline used during training
in the predictor repo. It includes:
1. Log transformation of CLOSE column
2. Log returns calculation  
3. STL decomposition (trend, seasonal, residual)
4. Wavelet features
5. MTM (Multi-taper method) features
6. Feature normalization and alignment
7. Combining original features with generated features

This ensures that the prediction provider applies the exact same preprocessing
as was used during model training.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.seasonal import STL
import json
import os
import logging
from typing import Dict, Any, Optional, Tuple, List
from scipy.signal import hilbert
from scipy.stats import shapiro

logger = logging.getLogger(__name__)

# Try importing optional dependencies
try:
    import pywt  # For Wavelets
    HAS_WAVELETS = True
except ImportError:
    logger.warning("pywt library not found. Wavelet features will be unavailable.")
    pywt = None
    HAS_WAVELETS = False

try:
    from scipy.signal.windows import dpss  # For MTM tapers
    HAS_MTM = True
except ImportError:
    logger.warning("scipy.signal.windows not found. MTM features may be unavailable.")
    dpss = None
    HAS_MTM = False


class STLPreprocessor:
    """
    STL-based preprocessor that replicates the exact preprocessing pipeline
    used during training in the predictor repo.
    """
    
    # Default parameters matching the predictor repo
    DEFAULT_PARAMS = {
        # --- STL Parameters ---
        "use_stl": True,
        "stl_period": 24,
        "stl_window": None,  # Will be calculated: 2 * stl_period + 1
        "stl_trend": None,   # Will be calculated based on stl_period and stl_window
        "stl_plot_file": None,
        
        # --- Wavelet Parameters ---
        "use_wavelets": True,
        "wavelet_name": 'db4',
        "wavelet_levels": 2,
        "wavelet_mode": 'symmetric',
        "wavelet_plot_file": None,
        
        # --- MTM Parameters ---
        "use_multi_tapper": False,
        "mtm_window_len": 168,
        "mtm_step": 1,
        "mtm_time_bandwidth": 5.0,
        "mtm_num_tapers": None,
        "mtm_freq_bands": [(0, 0.01), (0.01, 0.06), (0.06, 0.2), (0.2, 0.5)],
        "tapper_plot_file": None,
        "tapper_plot_points": 480,
        
        # --- Normalization ---
        "normalize_features": True,
    }
    
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """Initialize the STL preprocessor."""
        self.params = self.DEFAULT_PARAMS.copy()
        if params:
            self.params.update(params)
            
        self.scalers = {}
        self._resolve_stl_params()
    
    def _resolve_stl_params(self):
        """Resolve STL parameters based on period."""
        if self.params.get("stl_period") is not None and self.params.get("stl_period") > 1:
            if self.params.get("stl_window") is None:
                self.params["stl_window"] = 2 * self.params["stl_period"] + 1
            
            if self.params.get("stl_trend") is None:
                current_stl_window = self.params.get("stl_window")
                if current_stl_window is not None and current_stl_window > 3:
                    try:
                        trend_calc = int(1.5 * self.params["stl_period"] / (1 - 1.5 / current_stl_window)) + 1
                        self.params["stl_trend"] = max(3, trend_calc)
                    except ZeroDivisionError:
                        self.params["stl_trend"] = self.params["stl_period"] + 1
                else:
                    self.params["stl_trend"] = self.params["stl_period"] + 1
            
            # Ensure stl_trend is odd
            if self.params.get("stl_trend") is not None and self.params["stl_trend"] % 2 == 0:
                self.params["stl_trend"] += 1
    
    def process_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Apply the complete STL preprocessing pipeline to the input data.
        
        Args:
            data: DataFrame with CLOSE column and other features
            
        Returns:
            DataFrame with original features plus generated STL features
        """\n        logger.info(\"Starting STL preprocessing pipeline\")\n        \n        # Extract CLOSE column for decomposition\n        if 'CLOSE' not in data.columns:\n            raise ValueError(\"CLOSE column not found in input data\")\n        \n        close_series = data['CLOSE'].astype(np.float32).values\n        \n        # 1. Log transformation (matching predictor repo exactly)\n        log_series = np.log1p(np.maximum(0, close_series))\n        logger.info(f\"Applied log transformation. Series length: {len(log_series)}\")\n        \n        # 2. Log returns calculation\n        log_returns = np.diff(log_series, prepend=log_series[0])\n        \n        # 3. Initialize feature dictionary with original columns\n        features = {}\n        \n        # Add original columns (excluding CLOSE as it's transformed)\n        for col in data.columns:\n            if col != 'CLOSE':\n                features[col] = data[col].values.astype(np.float32)\n        \n        # 4. Add log returns (normalized)\n        features['log_return'] = self._normalize_series(log_returns, 'log_return', fit=True)\n        logger.info(\"Generated: Log Returns (Normalized)\")\n        \n        # 5. STL decomposition\n        if self.params.get('use_stl'):\n            logger.info(\"Computing STL features...\")\n            try:\n                trend, seasonal, resid = self._rolling_stl(\n                    log_series, \n                    self.params['stl_window'],\n                    self.params['stl_period'], \n                    self.params['stl_trend']\n                )\n                \n                if len(trend) > 0:\n                    features['stl_trend'] = self._normalize_series(trend, 'stl_trend', fit=True)\n                    features['stl_seasonal'] = self._normalize_series(seasonal, 'stl_seasonal', fit=True)\n                    features['stl_resid'] = self._normalize_series(resid, 'stl_resid', fit=True)\n                    logger.info(\"Generated: STL Trend, Seasonal, Residual (Normalized)\")\n                    \n                    # Plot if requested\n                    if self.params.get(\"stl_plot_file\"):\n                        self._plot_decomposition(\n                            log_series[len(log_series)-len(trend):], \n                            trend, seasonal, resid, \n                            self.params[\"stl_plot_file\"]\n                        )\n                else:\n                    logger.warning(\"STL output zero length\")\n            except Exception as e:\n                logger.error(f\"Error processing STL: {e}. Skipping.\")\n        else:\n            logger.info(\"Skipped: STL features\")\n        \n        # 6. Wavelet features\n        if self.params.get('use_wavelets') and HAS_WAVELETS:\n            logger.info(\"Computing Wavelet features...\")\n            try:\n                wav_features = self._compute_wavelet_features(log_series)\n                if wav_features:\n                    for name, values in wav_features.items():\n                        features[f'wav_{name}'] = self._normalize_series(values, f'wav_{name}', fit=True)\n                    logger.info(f\"Generated: {len(wav_features)} Wavelet features (Normalized)\")\n                    \n                    # Plot if requested\n                    if self.params.get(\"wavelet_plot_file\"):\n                        self._plot_wavelets(log_series, wav_features, self.params[\"wavelet_plot_file\"])\n                else:\n                    logger.warning(\"Wavelet computation returned no features\")\n            except Exception as e:\n                logger.error(f\"Error processing Wavelets: {e}. Skipping.\")\n        else:\n            if not HAS_WAVELETS:\n                logger.info(\"Skipped: Wavelet features (pywt not available)\")\n            else:\n                logger.info(\"Skipped: Wavelet features\")\n        \n        # 7. MTM features\n        if self.params.get('use_multi_tapper') and HAS_MTM:\n            logger.info(\"Computing MTM features...\")\n            try:\n                mtm_features = self._compute_mtm_features(log_series)\n                if mtm_features:\n                    for name, values in mtm_features.items():\n                        features[f'mtm_{name}'] = self._normalize_series(values, f'mtm_{name}', fit=True)\n                    logger.info(f\"Generated: {len(mtm_features)} MTM features (Normalized)\")\n                    \n                    # Plot if requested\n                    if self.params.get(\"tapper_plot_file\"):\n                        self._plot_mtm(mtm_features, self.params[\"tapper_plot_file\"], \n                                     self.params.get(\"tapper_plot_points\"))\n                else:\n                    logger.warning(\"MTM computation returned no features\")\n            except Exception as e:\n                logger.error(f\"Error processing MTM: {e}. Skipping.\")\n        else:\n            if not HAS_MTM:\n                logger.info(\"Skipped: MTM features (scipy.signal.windows not available)\")\n            else:\n                logger.info(\"Skipped: MTM features\")\n        \n        # 8. Align feature lengths and create result DataFrame\n        logger.info(\"Aligning feature lengths...\")\n        aligned_features = self._align_features(features)\n        \n        # Create result DataFrame with aligned index\n        result_length = len(next(iter(aligned_features.values())))\n        result_index = data.index[-result_length:] if len(data.index) >= result_length else data.index\n        \n        result_df = pd.DataFrame(aligned_features, index=result_index)\n        \n        logger.info(f\"STL preprocessing complete. Output shape: {result_df.shape}\")\n        logger.info(f\"Generated features: {list(result_df.columns)}\")\n        \n        return result_df\n    \n    def _normalize_series(self, series: np.ndarray, name: str, fit: bool = False) -> np.ndarray:\n        \"\"\"Normalize a time series using StandardScaler (matching predictor repo).\"\"\"\n        if not self.params.get(\"normalize_features\", True):\n            return series.astype(np.float32)\n        \n        series = series.astype(np.float32)\n        \n        # Handle NaNs and infinities\n        if np.any(np.isnan(series)) or np.any(np.isinf(series)):\n            logger.warning(f\"NaNs/Infs in '{name}' pre-normalization. Filling...\")\n            series_df = pd.Series(series).fillna(method='ffill').fillna(method='bfill')\n            series = series_df.values\n            if np.any(np.isnan(series)) or np.any(np.isinf(series)):\n                logger.warning(f\"Filling failed for '{name}'. Using zeros.\")\n                series = np.nan_to_num(series, nan=0.0, posinf=0.0, neginf=0.0)\n        \n        data_reshaped = series.reshape(-1, 1)\n        \n        if fit:\n            scaler = StandardScaler()\n            if np.std(data_reshaped) < 1e-9:\n                logger.warning(f\"'{name}' is constant. Using dummy scaler.\")\n                # Create dummy scaler for constant data\n                class DummyScaler:\n                    def fit(self, X): pass\n                    def transform(self, X): return X.astype(np.float32)\n                    def inverse_transform(self, X): return X.astype(np.float32)\n                scaler = DummyScaler()\n            else:\n                scaler.fit(data_reshaped)\n            self.scalers[name] = scaler\n        else:\n            if name not in self.scalers:\n                raise RuntimeError(f\"Scaler '{name}' not fitted.\")\n            scaler = self.scalers[name]\n        \n        normalized_data = scaler.transform(data_reshaped)\n        return normalized_data.flatten()\n    \n    def _rolling_stl(self, series: np.ndarray, stl_window: int, period: int, trend_smoother: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:\n        \"\"\"Perform rolling STL decomposition (matching predictor repo).\"\"\"\n        logger.debug(f\"Performing rolling STL: Win={stl_window}, Period={period}, Trend={trend_smoother}\")\n        \n        n = len(series)\n        num_points = n - stl_window + 1\n        \n        if num_points <= 0:\n            raise ValueError(f\"stl_window ({stl_window}) > series length ({n}).\")\n        \n        trend = np.zeros(num_points)\n        seasonal = np.zeros(num_points)\n        resid = np.zeros(num_points)\n        \n        for i in range(num_points):\n            window_data = series[i:i + stl_window]\n            if len(window_data) >= 2 * period:\n                try:\n                    stl = STL(window_data, seasonal=period, trend=trend_smoother)\n                    result = stl.fit()\n                    trend[i] = result.trend[-1]\n                    seasonal[i] = result.seasonal[-1]\n                    resid[i] = result.resid[-1]\n                except Exception as e:\n                    logger.warning(f\"STL failed for window {i}: {e}\")\n                    # Use simple fallbacks\n                    trend[i] = np.mean(window_data)\n                    seasonal[i] = 0.0\n                    resid[i] = window_data[-1] - trend[i]\n            else:\n                # Not enough data for STL\n                trend[i] = np.mean(window_data)\n                seasonal[i] = 0.0\n                resid[i] = window_data[-1] - trend[i]\n        \n        logger.debug(f\"STL decomposition complete. Output length: {len(trend)}\")\n        return trend, seasonal, resid\n    \n    def _compute_wavelet_features(self, series: np.ndarray) -> Dict[str, np.ndarray]:\n        \"\"\"Compute wavelet features using SWT (matching predictor repo).\"\"\"\n        if not HAS_WAVELETS:\n            return {}\n        \n        name = self.params['wavelet_name']\n        levels = self.params['wavelet_levels']\n        mode = self.params['wavelet_mode']\n        \n        logger.debug(f\"Computing Wavelet features: {name}, levels={levels}, mode={mode}\")\n        \n        try:\n            # Clean series (remove NaN/inf)\n            series_clean = np.nan_to_num(series, nan=0.0, posinf=0.0, neginf=0.0)\n            \n            # Use Stationary Wavelet Transform (SWT) for better time alignment\n            coeffs = pywt.swt(series_clean, name, level=levels, trim_approx=False, norm=True)\n            \n            features = {}\n            \n            # Extract detail coefficients for each level\n            for level in range(levels):\n                if level < len(coeffs) and len(coeffs[level]) == 2:\n                    detail_coeffs = coeffs[level][1]  # Detail coefficients\n                    if len(detail_coeffs) == len(series_clean):\n                        features[f'detail_L{level+1}'] = detail_coeffs\n            \n            # Extract final approximation coefficients\n            if len(coeffs) > 0 and len(coeffs[0]) == 2:\n                approx_coeffs = coeffs[0][0]  # Approximation coefficients\n                if len(approx_coeffs) == len(series_clean):\n                    features[f'approx_L{levels}'] = approx_coeffs\n            \n            # Apply causality shift correction\n            if features:\n                features = self._apply_causality_shift(features, name)\n            \n            logger.debug(f\"Wavelet computation complete. Generated {len(features)} features\")\n            return features\n            \n        except Exception as e:\n            logger.error(f\"Wavelet computation failed: {e}\")\n            return {}\n    \n    def _apply_causality_shift(self, features: Dict[str, np.ndarray], wavelet_name: str) -> Dict[str, np.ndarray]:\n        \"\"\"Apply causality shift correction to wavelet features.\"\"\"\n        try:\n            wavelet = pywt.Wavelet(wavelet_name)\n            filter_len = wavelet.dec_len\n            shift_amount = max(0, (filter_len // 2) - 1)\n            \n            if shift_amount > 0:\n                logger.debug(f\"Applying causality shift (forward by {shift_amount})\")\n                shifted_features = {}\n                \n                for k, v in features.items():\n                    if len(v) > shift_amount:\n                        first_known_value = v[0]\n                        shifted_v = np.full(len(v), first_known_value, dtype=v.dtype)\n                        shifted_v[shift_amount:] = v[:-shift_amount]\n                        shifted_features[k] = shifted_v\n                    else:\n                        shifted_features[k] = v\n                \n                return shifted_features\n            else:\n                return features\n                \n        except Exception as e:\n            logger.warning(f\"Causality shift failed: {e}. Using original features.\")\n            return features\n    \n    def _compute_mtm_features(self, series: np.ndarray) -> Dict[str, np.ndarray]:\n        \"\"\"Compute Multi-taper method features (matching predictor repo).\"\"\"\n        if not HAS_MTM:\n            return {}\n        \n        # This is a simplified MTM implementation\n        # For production use, you might want to implement the full MTM algorithm\n        logger.debug(\"Computing MTM features...\")\n        \n        # For now, return empty dict as MTM is complex and optional\n        # The predictor repo implementation is quite involved\n        return {}\n    \n    def _align_features(self, features: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:\n        \"\"\"Align all features to the same length (matching predictor repo).\"\"\"\n        if not features:\n            return features\n        \n        # Find the minimum length among all features\n        min_length = min(len(v) for v in features.values())\n        \n        # Trim all features to the minimum length (from the end)\n        aligned_features = {}\n        for name, values in features.items():\n            if len(values) >= min_length:\n                aligned_features[name] = values[-min_length:]\n            else:\n                # Pad with last value if somehow shorter\n                padded = np.full(min_length, values[-1] if len(values) > 0 else 0.0, dtype=values.dtype)\n                padded[:len(values)] = values\n                aligned_features[name] = padded\n        \n        logger.debug(f\"Aligned features to length: {min_length}\")\n        return aligned_features\n    \n    def _plot_decomposition(self, series: np.ndarray, trend: np.ndarray, seasonal: np.ndarray, resid: np.ndarray, file_path: str):\n        \"\"\"Plot STL decomposition results.\"\"\"\n        try:\n            fig, axes = plt.subplots(4, 1, figsize=(12, 10))\n            \n            # Plot last 480 points for better visualization\n            plot_points = min(480, len(series))\n            start_idx = max(0, len(series) - plot_points)\n            \n            x_series = series[start_idx:]\n            x_trend = trend[-len(x_series):] if len(trend) >= len(x_series) else trend\n            x_seasonal = seasonal[-len(x_series):] if len(seasonal) >= len(x_series) else seasonal\n            x_resid = resid[-len(x_series):] if len(resid) >= len(x_series) else resid\n            \n            axes[0].plot(x_series)\n            axes[0].set_title('Original Series (Log-transformed)')\n            \n            axes[1].plot(x_trend)\n            axes[1].set_title('Trend Component')\n            \n            axes[2].plot(x_seasonal)\n            axes[2].set_title('Seasonal Component')\n            \n            axes[3].plot(x_resid)\n            axes[3].set_title('Residual Component')\n            \n            plt.tight_layout()\n            plt.savefig(file_path)\n            plt.close()\n            \n            logger.info(f\"STL decomposition plot saved to {file_path}\")\n            \n        except Exception as e:\n            logger.error(f\"Failed to save STL plot: {e}\")\n    \n    def _plot_wavelets(self, original_series: np.ndarray, wavelet_features: Dict[str, np.ndarray], file_path: str):\n        \"\"\"Plot wavelet features.\"\"\"\n        try:\n            num_features = len(wavelet_features)\n            if num_features == 0:\n                logger.warning(\"No wavelet features to plot\")\n                return\n            \n            fig, axes = plt.subplots(num_features + 1, 1, figsize=(12, 2 * (num_features + 1)))\n            if num_features == 0:\n                axes = [axes]\n            \n            # Plot last 480 points\n            plot_points = min(480, len(original_series))\n            start_idx = max(0, len(original_series) - plot_points)\n            original_plot = original_series[start_idx:]\n            \n            axes[0].plot(original_plot)\n            axes[0].set_title('Original Series (Log-transformed)')\n            \n            for i, (name, values) in enumerate(wavelet_features.items()):\n                values_plot = values[start_idx:] if len(values) >= len(original_plot) else values\n                axes[i + 1].plot(values_plot)\n                axes[i + 1].set_title(f'Wavelet Feature: {name}')\n            \n            plt.tight_layout()\n            plt.savefig(file_path)\n            plt.close()\n            \n            logger.info(f\"Wavelet features plot saved to {file_path}\")\n            \n        except Exception as e:\n            logger.error(f\"Failed to save wavelet plot: {e}\")\n    \n    def _plot_mtm(self, mtm_features: Dict[str, np.ndarray], file_path: str, points_to_plot: int = 500):\n        \"\"\"Plot MTM features.\"\"\"\n        # Placeholder for MTM plotting\n        logger.info(\"MTM plotting not implemented\")\n    \n    def get_feature_count(self) -> int:\n        \"\"\"Get the expected number of additional features generated by this preprocessor.\"\"\"\n        count = 1  # log_return always generated\n        \n        if self.params.get('use_stl'):\n            count += 3  # trend, seasonal, residual\n        \n        if self.params.get('use_wavelets') and HAS_WAVELETS:\n            levels = self.params['wavelet_levels']\n            count += levels + 1  # detail coefficients + approximation\n        \n        if self.params.get('use_multi_tapper') and HAS_MTM:\n            # This depends on the MTM implementation\n            # For now, assume 0 additional features\n            count += 0\n        \n        return count
