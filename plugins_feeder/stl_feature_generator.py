"""
STL Feature Generator Plugin for Prediction Provider

This module generates additional features from the CLOSE column to match
the preprocessing done during model training in the predictor repo.

Based on predictor/preprocessor_plugins/stl_preprocessor.py
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.seasonal import STL
import logging
from typing import Dict, Optional, Tuple

# Try importing optional dependencies
try:
    import pywt
    HAS_WAVELETS = True
except ImportError:
    HAS_WAVELETS = False

try:
    from scipy.signal.windows import dpss
    HAS_MTM = True
except ImportError:
    HAS_MTM = False

logger = logging.getLogger(__name__)


class STLFeatureGenerator:
    """Generates STL, wavelet, and MTM features from CLOSE column to match predictor preprocessing."""
    
    def __init__(self):
        # Default parameters matching predictor/preprocessor_plugins/stl_preprocessor.py
        self.params = {
            # STL Parameters
            "use_stl": False,
            "stl_period": 24,
            "stl_window": None,  # Will be calculated as 2 * stl_period + 1
            "stl_trend": None,   # Will be calculated based on stl_period and stl_window
            
            # Wavelet Parameters
            "use_wavelets": True,
            "wavelet_name": 'db4',
            "wavelet_levels": 2,
            "wavelet_mode": 'symmetric',
            
            # MTM Parameters
            "use_multi_tapper": False,
            "mtm_window_len": 168,
            "mtm_step": 1,
            "mtm_time_bandwidth": 5.0,
            "mtm_num_tapers": None,
            "mtm_freq_bands": [(0, 0.01), (0.01, 0.06), (0.06, 0.2), (0.2, 0.5)],
            
            # Normalization
            "normalize_features": True,
        }
        self.scalers = {}
    
    def set_params(self, **kwargs):
        """Update parameters and resolve defaults."""
        for key, value in kwargs.items():
            if key in self.params:
                self.params[key] = value
        
        # Resolve STL parameters
        if self.params.get("stl_period") is not None and self.params.get("stl_period") > 1:
            if self.params.get("stl_window") is None:
                self.params["stl_window"] = 2 * self.params["stl_period"] + 1
            
            if self.params.get("stl_trend") is None:
                stl_window = self.params.get("stl_window")
                if stl_window is not None and stl_window > 3:
                    try:
                        trend_calc = int(1.5 * self.params["stl_period"] / (1 - 1.5 / stl_window)) + 1
                        self.params["stl_trend"] = max(3, trend_calc)
                    except ZeroDivisionError:
                        self.params["stl_trend"] = self.params["stl_period"] + 1
                else:
                    self.params["stl_trend"] = self.params["stl_period"] + 1
            
            # Ensure odd number for stl_trend
            if self.params.get("stl_trend") is not None and self.params["stl_trend"] % 2 == 0:
                self.params["stl_trend"] += 1
    
    def _normalize_series(self, series: np.ndarray, name: str, fit: bool = False) -> np.ndarray:
        """Normalize a time series using StandardScaler."""
        if not self.params.get("normalize_features", True):
            return series.astype(np.float32)
        
        series = series.astype(np.float32)
        
        # Handle NaNs/Infs
        if np.any(np.isnan(series)) or np.any(np.isinf(series)):
            logger.warning(f"NaNs/Infs found in '{name}' before normalization. Filling...")
            series = pd.Series(series).fillna(method='ffill').fillna(method='bfill').values
            if np.any(np.isnan(series)) or np.any(np.isinf(series)):
                logger.warning(f"Failed to fill NaNs/Infs in '{name}'. Using zeros.")
                series = np.nan_to_num(series, nan=0.0, posinf=0.0, neginf=0.0)
        
        data_reshaped = series.reshape(-1, 1)
        
        if fit:
            scaler = StandardScaler()
            if np.std(data_reshaped) < 1e-9:
                logger.warning(f"'{name}' appears constant. Using dummy scaler.")
                class DummyScaler:
                    def fit(self, X): pass
                    def transform(self, X): return X.astype(np.float32)
                    def inverse_transform(self, X): return X.astype(np.float32)
                scaler = DummyScaler()
            else:
                scaler.fit(data_reshaped)
            self.scalers[name] = scaler
        else:
            if name not in self.scalers:
                raise RuntimeError(f"Scaler '{name}' not fitted.")
            scaler = self.scalers[name]
        
        normalized_data = scaler.transform(data_reshaped)
        return normalized_data.flatten()
    
    def _rolling_stl(self, series: np.ndarray, stl_window: int, period: int, trend_smoother: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Perform rolling STL decomposition."""
        logger.debug(f"Performing rolling STL: Win={stl_window}, Period={period}, Trend={trend_smoother}")
        
        n = len(series)
        num_points = n - stl_window + 1
        if num_points <= 0:
            raise ValueError(f"stl_window ({stl_window}) > series length ({n}).")
        
        trend = np.zeros(num_points)
        seasonal = np.zeros(num_points)
        resid = np.zeros(num_points)
        
        for i in range(num_points):
            window_data = series[i:i + stl_window]
            
            if len(window_data) >= 2 * period:
                try:
                    stl = STL(window_data, seasonal=13, trend=trend_smoother, period=period)
                    result = stl.fit()
                    trend[i] = result.trend[-1]
                    seasonal[i] = result.seasonal[-1]
                    resid[i] = result.resid[-1]
                except Exception as e:
                    logger.debug(f"STL failed for window {i}: {e}. Using fallback.")
                    trend[i] = np.mean(window_data)
                    seasonal[i] = 0.0
                    resid[i] = window_data[-1] - trend[i]
            else:
                # Not enough data for STL
                trend[i] = np.mean(window_data)
                seasonal[i] = 0.0
                resid[i] = window_data[-1] - trend[i]
        
        logger.debug(f"STL decomposition complete. Output length: {len(trend)}")
        return trend, seasonal, resid
    
    def _compute_wavelet_features(self, series: np.ndarray) -> Dict[str, np.ndarray]:
        """Compute wavelet features using SWT (matching predictor repo)."""
        if not HAS_WAVELETS:
            logger.warning("pywt not available. Skipping wavelet features.")
            return {}
        
        name = self.params['wavelet_name']
        levels = self.params['wavelet_levels']
        mode = self.params['wavelet_mode']
        
        logger.debug(f"Computing Wavelet features: {name}, levels={levels}, mode={mode}")
        
        try:
            # Clean series
            clean_series = np.nan_to_num(series, nan=0.0, posinf=0.0, neginf=0.0)
            
            # Ensure length is power of 2 for better performance
            n = len(clean_series)
            next_pow2 = 2 ** int(np.ceil(np.log2(n)))
            if n < next_pow2:
                padded_series = np.pad(clean_series, (0, next_pow2 - n), mode='constant', constant_values=0)
            else:
                padded_series = clean_series
            
            # Perform SWT (Stationary Wavelet Transform)
            coeffs = pywt.swt(padded_series, name, level=levels, trim_approx=False)
            
            features = {}
            for level in range(levels):
                cA, cD = coeffs[level]
                
                # Trim back to original length
                cA = cA[:n]
                cD = cD[:n]
                
                # Compute statistics for approximation and detail coefficients
                features[f'swt_cA_L{level+1}_mean'] = np.full(n, np.mean(cA))
                features[f'swt_cA_L{level+1}_std'] = np.full(n, np.std(cA))
                features[f'swt_cA_L{level+1}_energy'] = np.full(n, np.sum(cA**2))
                
                features[f'swt_cD_L{level+1}_mean'] = np.full(n, np.mean(cD))
                features[f'swt_cD_L{level+1}_std'] = np.full(n, np.std(cD))
                features[f'swt_cD_L{level+1}_energy'] = np.full(n, np.sum(cD**2))
            
            logger.debug(f"Wavelet features computed: {list(features.keys())}")
            return features
            
        except Exception as e:
            logger.error(f"Error during Wavelet computation: {e}")
            return {}
    
    def _compute_mtm_features(self, series: np.ndarray) -> Dict[str, np.ndarray]:
        """Compute multitaper method features."""
        if not HAS_MTM:
            logger.warning("scipy.signal.windows not available. Skipping MTM features.")
            return {}
        
        window_len = self.params['mtm_window_len']
        step = self.params['mtm_step']
        time_bandwidth = self.params['mtm_time_bandwidth']
        freq_bands = self.params['mtm_freq_bands']
        
        logger.debug(f"Computing MTM features: window={window_len}, step={step}, NW={time_bandwidth}")
        
        try:
            n = len(series)
            num_windows = max(1, (n - window_len) // step + 1)
            
            features = {}
            for band_idx, (f_low, f_high) in enumerate(freq_bands):
                band_power = np.zeros(n)
                
                for i in range(num_windows):
                    start_idx = i * step
                    end_idx = min(start_idx + window_len, n)
                    window_data = series[start_idx:end_idx]
                    
                    if len(window_data) >= window_len // 2:
                        # Compute power spectral density
                        fft_data = np.fft.fft(window_data)
                        freqs = np.fft.fftfreq(len(window_data))
                        power = np.abs(fft_data) ** 2
                        
                        # Filter frequency band
                        band_mask = (freqs >= f_low) & (freqs <= f_high)
                        band_power_val = np.mean(power[band_mask]) if np.any(band_mask) else 0.0
                        
                        # Fill the corresponding time indices
                        fill_start = start_idx
                        fill_end = min(start_idx + window_len, n)
                        band_power[fill_start:fill_end] = band_power_val
                
                features[f'mtm_band_{band_idx}_power'] = band_power
            
            logger.debug(f"MTM features computed: {list(features.keys())}")
            return features
            
        except Exception as e:
            logger.error(f"Error during MTM computation: {e}")
            return {}
    
    def align_features(self, features: Dict[str, np.ndarray], target_length: int) -> Dict[str, np.ndarray]:
        """Align all features to the same length by trimming from the beginning."""
        aligned_features = {}
        
        for name, values in features.items():
            if len(values) > target_length:
                aligned_features[name] = values[-target_length:]
            elif len(values) < target_length:
                # Pad with last value if shorter
                padding = np.full(target_length - len(values), values[-1] if len(values) > 0 else 0.0)
                aligned_features[name] = np.concatenate([padding, values])
            else:
                aligned_features[name] = values
        
        return aligned_features
    
    def generate_features(self, close_series: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Generate additional features from CLOSE column to match predictor preprocessing.
        
        Args:
            close_series: Array of CLOSE prices
            
        Returns:
            Dictionary containing generated features
        """
        logger.info("Generating STL features for CLOSE column...")
        
        # 1. Log transformation
        log_series = np.log1p(np.maximum(0, close_series))
        logger.debug(f"Log transform applied. Series length: {len(log_series)}")
        
        # 2. Initialize features dict
        features = {}
        
        # 3. Log returns
        log_returns = np.diff(log_series, prepend=log_series[0])
        features['log_return'] = self._normalize_series(log_returns, 'log_return', fit=True)
        logger.debug("Generated: Log Returns (Normalized)")
        
        # 4. STL decomposition (if enabled)
        if self.params.get('use_stl'):
            logger.info("Computing STL features...")
            try:
                stl_window = self.params['stl_window']
                stl_period = self.params['stl_period']
                stl_trend = self.params['stl_trend']
                
                trend, seasonal, resid = self._rolling_stl(log_series, stl_window, stl_period, stl_trend)
                
                if len(trend) > 0:
                    features['stl_trend'] = self._normalize_series(trend, 'stl_trend', fit=True)
                    features['stl_seasonal'] = self._normalize_series(seasonal, 'stl_seasonal', fit=True)
                    features['stl_resid'] = self._normalize_series(resid, 'stl_resid', fit=True)
                    logger.info("Generated: STL Trend, Seasonal, Residual (Normalized)")
                else:
                    logger.warning("STL output zero length")
            except Exception as e:
                logger.error(f"Error processing STL: {e}. Skipping.")
        else:
            logger.info("Skipped: STL features")
        
        # 5. Wavelet features (if enabled)
        if self.params.get('use_wavelets') and HAS_WAVELETS:
            logger.info("Computing Wavelet features...")
            try:
                wav_features = self._compute_wavelet_features(log_series)
                if wav_features:
                    for name, values in wav_features.items():
                        features[f'wav_{name}'] = self._normalize_series(values, f'wav_{name}', fit=True)
                    logger.info(f"Generated: {len(wav_features)} Wavelet features (Normalized)")
                else:
                    logger.warning("Wavelet computation returned no features")
            except Exception as e:
                logger.error(f"Error processing Wavelets: {e}. Skipping.")
        else:
            logger.info("Skipped: Wavelet features")
        
        # 6. MTM features (if enabled)
        if self.params.get('use_multi_tapper') and HAS_MTM:
            logger.info("Computing MTM features...")
            try:
                mtm_features = self._compute_mtm_features(log_series)
                if mtm_features:
                    for name, values in mtm_features.items():
                        features[f'mtm_{name}'] = self._normalize_series(values, f'mtm_{name}', fit=True)
                    logger.info(f"Generated: {len(mtm_features)} MTM features (Normalized)")
                else:
                    logger.warning("MTM computation returned no features")
            except Exception as e:
                logger.error(f"Error processing MTM: {e}. Skipping.")
        else:
            logger.info("Skipped: MTM features")
        
        # 7. Align feature lengths
        if features:
            base_length = len(features['log_return'])
            features = self.align_features(features, base_length)
            logger.info(f"Features aligned to length: {base_length}")
        
        logger.info(f"Feature generation complete. Generated {len(features)} features: {list(features.keys())}")
        return features
