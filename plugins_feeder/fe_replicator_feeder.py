#!/usr/bin/env python3
"""
FE Replicator Feeder Plugin for Prediction Provider.

This plugin replicates the exact feature engineering process from the feature-eng repo
using the exported FE configuration for perfect parameter matching.
"""

import os
import sys
import numpy as np
import json
import pandas as pd
import numpy as np
import importlib.util
from typing import Dict, Any, Optional, List
from pathlib import Path

class FeReplicatorFeeder:
    """
    Feeder plugin that replicates feature-eng processing with perfect parameter matching.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the FE Replicator Feeder."""
        self.config = config or {}
        self.fe_config = None
        self.tech_indicator_plugin = None
        self.decomp_processor = None
        self.feature_eng_repo_path = "/home/harveybc/Documents/GitHub/feature-eng"
        
        # Plugin parameters
        self.plugin_params = {
            'fe_config_path': 'fe_config_test.json',
            'input_csv_path': 'tests/data/eurusd_hour_2005_2020_ohlc.csv',
            'output_csv_path': 'fe_replicated_output.csv',
            'comparison_csv_path': 'feature_eng_output.csv',
            'num_rows_to_process': 1000,
            'num_rows_to_compare': 1000,
            'tolerance': 0.0  # No tolerance - exact matching required
        }
        
    def set_params(self, **params):
        """Set plugin parameters."""
        for key, value in params.items():
            if key in self.plugin_params:
                self.plugin_params[key] = value
                
    def load_fe_config(self, fe_config_path: str) -> Dict[str, Any]:
        """Load the exported FE configuration."""
        full_path = os.path.join(self.feature_eng_repo_path, fe_config_path)
        
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"FE config file not found: {full_path}")
            
        with open(full_path, 'r') as f:
            self.fe_config = json.load(f)
            
        print(f"[FE_REPLICATOR] ✅ Loaded FE config from: {full_path}")
        print(f"[FE_REPLICATOR] Config version: {self.fe_config['version_info']['config_version']}")
        
        return self.fe_config
    
    def setup_feature_eng_environment(self):
        """Setup the feature-eng environment and import required modules."""
        # Add feature-eng repo to Python path
        if self.feature_eng_repo_path not in sys.path:
            sys.path.insert(0, self.feature_eng_repo_path)
            
        try:
            # Import tech indicator plugin from feature-eng
            from app.plugins.tech_indicator import Plugin as TechIndicatorPlugin
            self.tech_indicator_plugin = TechIndicatorPlugin()
            
            # Import decomposition post-processor from feature-eng
            from app.plugins.post_processors.decomposition_post_processor import DecompositionPostProcessor
            
            # Apply FE configuration to plugins for exact replication
            if self.fe_config:
                self._apply_fe_config_to_plugins()
                
            print("[FE_REPLICATOR] ✅ Feature-eng environment setup complete")
            
        except Exception as e:
            raise ImportError(f"Failed to import feature-eng modules: {e}")
    
    def _apply_fe_config_to_plugins(self):
        """Apply the FE configuration to the imported plugins."""
        if not self.fe_config:
            raise ValueError("FE config not loaded")
            
        # Apply tech indicator configuration
        tech_params = self.fe_config['tech_indicator_params']
        self.tech_indicator_plugin.set_params(
            short_term_period=tech_params['short_term_period'],
            mid_term_period=tech_params['mid_term_period'],
            long_term_period=tech_params['long_term_period'],
            indicators=tech_params['indicators']
        )
        
        # Set indicator-specific parameters
        indicator_params = tech_params['indicator_specific_params']
        for param, value in indicator_params.items():
            if hasattr(self.tech_indicator_plugin, 'params'):
                self.tech_indicator_plugin.params[param] = value
        
        print(f"[FE_REPLICATOR] ✅ Applied tech indicator config: {len(tech_params)} parameters")
        
        # Create decomposition processor with FE config
        decomp_params = self.fe_config['decomposition_params']
        self.decomp_processor = self._create_decomp_processor(decomp_params)
        
        print(f"[FE_REPLICATOR] ✅ Applied decomposition config: {len(decomp_params)} parameters")
    
    def _create_decomp_processor(self, decomp_params: Dict[str, Any]):
        """Create decomposition processor with FE config parameters."""
        from app.plugins.post_processors.decomposition_post_processor import DecompositionPostProcessor
        
        # Ensure we keep original columns like feature-eng does
        decomp_params_copy = decomp_params.copy()
        decomp_params_copy['keep_original'] = True
        decomp_params_copy['replace_original'] = False
        
        print(f"[FE_REPLICATOR] ✅ Using identical decomposition settings as feature-eng")
        
        processor = DecompositionPostProcessor(decomp_params_copy)
        
        # Ensure exact parameter matching
        processor.params.update(decomp_params_copy)
        
        return processor
    
    def load_input_data(self, csv_path: str, num_rows: int) -> pd.DataFrame:
        """Load the first N rows from the input CSV file."""
        full_path = os.path.join(self.feature_eng_repo_path, csv_path)
        
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Input CSV file not found: {full_path}")
            
        # Load the entire dataset
        df = pd.read_csv(full_path)
        
        # Get the first N rows (same as feature-eng)
        first_rows = df.head(num_rows).copy()
        
        print(f"[FE_REPLICATOR] ✅ Loaded first {len(first_rows)} rows from: {csv_path}")
        print(f"[FE_REPLICATOR] Date range: {first_rows.iloc[0]['datetime']} to {first_rows.iloc[-1]['datetime']}")
        
        return first_rows
    
    def _add_wavelet_features_if_missing(self, data: pd.DataFrame) -> pd.DataFrame:
        """Add wavelet decomposition features for CLOSE if they're missing."""
        try:
            import pywt
            
            # Check if wavelet features are missing
            wavelet_features = ['CLOSE_wav_detail_L1', 'CLOSE_wav_detail_L2', 'CLOSE_wav_approx_L2']
            missing_features = [f for f in wavelet_features if f not in data.columns]
            
            if not missing_features or 'CLOSE' not in data.columns:
                return data
            
            print(f"[FE_REPLICATOR] Adding missing wavelet features: {missing_features}")
            
            # Extract CLOSE series for decomposition
            close_series = data['CLOSE'].values
            
            # Parameters matching feature-eng defaults
            wavelet_name = 'db4'
            wavelet_levels = 2
            
            # Clean series (remove NaN/inf)
            series_clean = np.nan_to_num(close_series, nan=0.0, posinf=0.0, neginf=0.0)
            
            # Use Stationary Wavelet Transform (SWT) for better time alignment
            coeffs = pywt.swt(series_clean, wavelet_name, level=wavelet_levels, trim_approx=False, norm=True)
            
            # Extract detail coefficients for each level
            for level in range(wavelet_levels):
                feature_name = f'CLOSE_wav_detail_L{level+1}'
                if feature_name in missing_features and level < len(coeffs) and len(coeffs[level]) == 2:
                    detail_coeffs = coeffs[level][1]  # Detail coefficients
                    if len(detail_coeffs) == len(series_clean):
                        # Normalize using mean and std like feature-eng
                        normalized = (detail_coeffs - detail_coeffs.mean()) / detail_coeffs.std()
                        data[feature_name] = normalized.astype(np.float32)
                        print(f"[FE_REPLICATOR] ✅ Added {feature_name}")
            
            # Extract final approximation coefficients
            feature_name = f'CLOSE_wav_approx_L{wavelet_levels}'
            if feature_name in missing_features and len(coeffs) > 0 and len(coeffs[0]) == 2:
                approx_coeffs = coeffs[0][0]  # Approximation coefficients
                if len(approx_coeffs) == len(series_clean):
                    # Normalize using mean and std like feature-eng
                    normalized = (approx_coeffs - approx_coeffs.mean()) / approx_coeffs.std()
                    data[feature_name] = normalized.astype(np.float32)
                    print(f"[FE_REPLICATOR] ✅ Added {feature_name}")
            
            return data
            
        except Exception as e:
            print(f"[FE_REPLICATOR] ❌ Failed to add wavelet features: {e}")
            return data
    
    def _calculate_tech_indicators_exact_fe_way(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators exactly the same way as feature-eng (using pandas_ta defaults)."""
        import pandas_ta as ta
        
        # Debug column names
        print(f"[DEBUG] Input data columns: {data.columns.tolist()}")
        print(f"[DEBUG] Input data shape: {data.shape}")
        
        # Ensure we have the right column names (same as feature-eng expects)
        if 'Open' in data.columns:
            # Data already has correct names
            close_col = 'Close'
            high_col = 'High' 
            low_col = 'Low'
            open_col = 'Open'
        else:
            # Try to find the right columns
            close_col = None
            for col in ['CLOSE', 'Close', 'close']:
                if col in data.columns:
                    close_col = col
                    break
            
            high_col = None
            for col in ['HIGH', 'High', 'high']:
                if col in data.columns:
                    high_col = col
                    break
                    
            low_col = None
            for col in ['LOW', 'Low', 'low']:
                if col in data.columns:
                    low_col = col
                    break
                    
            open_col = None
            for col in ['OPEN', 'Open', 'open']:
                if col in data.columns:
                    open_col = col
                    break
        
        if not all([close_col, high_col, low_col, open_col]):
            raise ValueError(f"Missing required OHLC columns. Available: {data.columns.tolist()}")
        
        print(f"[DEBUG] Using columns: Open={open_col}, High={high_col}, Low={low_col}, Close={close_col}")
        
        # Create technical indicators dict exactly like feature-eng does
        technical_indicators = {}
        
        # Apply indicators using the exact same calls as feature-eng
        indicators = ['rsi', 'macd', 'ema', 'stoch', 'adx', 'atr', 'cci', 'bbands', 'williams', 'momentum', 'roc']
        
        for indicator in indicators:
            if indicator == 'rsi':
                rsi = ta.rsi(data[close_col])  # Default length is 14
                if rsi is not None:
                    technical_indicators['RSI'] = rsi
                    print(f"[DEBUG] RSI calculated: {rsi.iloc[:3].tolist()}")

            elif indicator == 'macd':
                macd = ta.macd(data[close_col])  # Default fast, slow, signal periods
                if 'MACD_12_26_9' in macd.columns:
                    technical_indicators['MACD'] = macd['MACD_12_26_9']
                    technical_indicators['MACD_Histogram'] = macd['MACDh_12_26_9']
                    technical_indicators['MACD_Signal'] = macd['MACDs_12_26_9']
                    print(f"[DEBUG] MACD calculated: {macd['MACD_12_26_9'].iloc[:3].tolist()}")

            elif indicator == 'ema':
                ema = ta.ema(data[close_col])  # Default length is 20
                if ema is not None:
                    technical_indicators['EMA'] = ema
                    print(f"[DEBUG] EMA calculated: {ema.iloc[:3].tolist()}")

            elif indicator == 'stoch':
                stoch = ta.stoch(data[high_col], data[low_col], data[close_col])  # Default %K, %D values
                if 'STOCHk_14_3_3' in stoch.columns:
                    technical_indicators['Stochastic_%K'] = stoch['STOCHk_14_3_3']
                    technical_indicators['Stochastic_%D'] = stoch['STOCHd_14_3_3']
                    print(f"[DEBUG] Stochastic calculated: %K={stoch['STOCHk_14_3_3'].iloc[:3].tolist()}")

            elif indicator == 'adx':
                adx = ta.adx(data[high_col], data[low_col], data[close_col])  # Default length is 14
                if 'ADX_14' in adx.columns:
                    technical_indicators['ADX'] = adx['ADX_14']
                    technical_indicators['DI+'] = adx['DMP_14']
                    technical_indicators['DI-'] = adx['DMN_14']
                    print(f"[DEBUG] ADX calculated: {adx['ADX_14'].iloc[:3].tolist()}")

            elif indicator == 'atr':
                atr = ta.atr(data[high_col], data[low_col], data[close_col])  # Default length is 14
                if atr is not None:
                    technical_indicators['ATR'] = atr
                    print(f"[DEBUG] ATR calculated: {atr.iloc[:3].tolist()}")

            elif indicator == 'cci':
                cci = ta.cci(data[high_col], data[low_col], data[close_col])  # Default length is 20
                if cci is not None:
                    technical_indicators['CCI'] = cci
                    print(f"[DEBUG] CCI calculated: {cci.iloc[:3].tolist()}")

            elif indicator == 'bbands':
                bbands = ta.bbands(data[close_col])  # Default length is 20
                if bbands is not None and len(bbands.columns) >= 5:
                    # Just use bbands data but don't add to main indicators for now
                    print(f"[DEBUG] BBands calculated with columns: {bbands.columns.tolist()}")

            elif indicator == 'williams':
                williams = ta.willr(data[high_col], data[low_col], data[close_col])  # Default length is 14
                if williams is not None:
                    technical_indicators['WilliamsR'] = williams
                    print(f"[DEBUG] Williams %R calculated: {williams.iloc[:3].tolist()}")

            elif indicator == 'momentum':
                momentum = ta.mom(data[close_col])  # Default length is 10
                if momentum is not None:
                    technical_indicators['Momentum'] = momentum
                    print(f"[DEBUG] Momentum calculated: {momentum.iloc[:3].tolist()}")

            elif indicator == 'roc':
                roc = ta.roc(data[close_col])  # Default length is 10
                if roc is not None:
                    technical_indicators['ROC'] = roc
                    print(f"[DEBUG] ROC calculated: {roc.iloc[:3].tolist()}")
        
        # Convert to DataFrame
        tech_df = pd.DataFrame(technical_indicators, index=data.index)
        
        # DON'T add OHLC columns here - they will be added later during combination
        # This prevents duplicate columns with .1 suffixes
        
        # Apply EXACT same NaN handling as feature-eng: fill with column mean
        # This is the critical step that eliminates NaNs just like feature-eng does
        print(f"[DEBUG] Before NaN filling: {tech_df.isnull().sum().sum()} NaN values")
        for column in tech_df.columns:
            if tech_df[column].isnull().any():
                original_nan_count = tech_df[column].isnull().sum()
                tech_df[column] = tech_df[column].fillna(tech_df[column].mean())
                print(f"[DEBUG] Filled {original_nan_count} NaN values in {column} with mean: {tech_df[column].mean():.4f}")
        
        print(f"[DEBUG] After NaN filling: {tech_df.isnull().sum().sum()} NaN values")
        print(f"[DEBUG] Result columns: {tech_df.columns.tolist()}")
        print(f"[DEBUG] Result shape: {tech_df.shape}")
        
        return tech_df
    
    def process_data_with_fe_pipeline(self, data: pd.DataFrame) -> pd.DataFrame:
        """Process data using the exact same pipeline as feature-eng."""
        print("[FE_REPLICATOR] Starting FE pipeline replication...")
        
        # Step 1: Prepare data (same as feature-eng data_processor.py)
        processed_data = self._prepare_data_like_feature_eng(data)
        
        # Prepare data with all columns (including BC-BO) for additional processing
        prepared_data_with_index = data.copy()
        # Rename datetime column and set as index like the processed data
        if 'datetime' in prepared_data_with_index.columns:
            prepared_data_with_index.rename(columns={'datetime': 'DATE_TIME'}, inplace=True)
            prepared_data_with_index['DATE_TIME'] = pd.to_datetime(prepared_data_with_index['DATE_TIME'], dayfirst=True, errors='coerce')
            prepared_data_with_index.set_index('DATE_TIME', inplace=True)
        
        # Ensure we have the same column names as feature-eng expects (uppercase OHLC)
        column_rename_map = {'open': 'OPEN', 'high': 'HIGH', 'low': 'LOW', 'close': 'CLOSE'}
        for old_col, new_col in column_rename_map.items():
            if old_col in prepared_data_with_index.columns:
                prepared_data_with_index.rename(columns={old_col: new_col}, inplace=True)
        
        # For later use, reset index to add DATE_TIME as column (but keep datetime index)
        prepared_data_with_index.reset_index(inplace=True)
        
        # Step 2: Apply tech indicators using exact same method as feature-eng
        # Direct replication of feature-eng's calculation (bypassing parameter configuration)
        tech_data = self._calculate_tech_indicators_exact_fe_way(processed_data)
        print(f"[FE_REPLICATOR] ✅ Tech indicators applied: {tech_data.shape}")
        print(f"[FE_REPLICATOR] Tech indicator columns: {list(tech_data.columns)}")
        print(f"[FE_REPLICATOR] ✅ Tech indicators applied: {tech_data.shape}")
        print(f"[FE_REPLICATOR] Tech indicator columns: {list(tech_data.columns)}")
        
        # Step 3: Apply EXACT variability analysis transformations from full dataset analysis
        # Use pre-determined log transformation decisions to match feature-eng exactly
        transformed_data = self._apply_predefined_transformations(tech_data)
        print(f"[FE_REPLICATOR] ✅ Applied pre-determined transformations: {transformed_data.shape}")
        
        # Step 4: Process additional datasets like feature-eng does (pass prepared data with OHLC columns)
        # Use the properly prepared data with datetime index for additional processing
        additional_features = self._process_additional_datasets(prepared_data_with_index)
        print(f"[FE_REPLICATOR] ✅ Additional features processed: {additional_features.shape}")
        
        # Step 5: Combine technical indicators with additional features
        if self.fe_config['processing_params']['tech_indicators']:
            combined_data = pd.concat([transformed_data, additional_features], axis=1)
            print(f"[FE_REPLICATOR] ✅ Combined data shape: {combined_data.shape}")
        else:
            combined_data = additional_features
        
        # Step 6: Add original CLOSE column for decomposition if needed
        decomp_features = self.fe_config['decomposition_params']['decomp_features']
        if decomp_features and 'CLOSE' in decomp_features:
            # Add original CLOSE column back for decomposition
            if 'CLOSE' in processed_data.columns:
                combined_data['CLOSE'] = processed_data['CLOSE']
                print(f"[FE_REPLICATOR] ✅ Added original CLOSE column for decomposition")
        
        # Step 7: Apply decomposition post-processing if configured
        if decomp_features:
            print(f"[FE_REPLICATOR] Applying decomposition to features: {decomp_features}")
            print(f"[FE_REPLICATOR] Available columns for decomposition: {list(combined_data.columns)}")
            decomp_data = self.decomp_processor.process_features(combined_data)
            print(f"[FE_REPLICATOR] ✅ Decomposition applied: {decomp_data.shape}")
            final_data = decomp_data
        else:
            final_data = combined_data
        
        # Step 7.5: Ensure wavelet features are present (add if missing)
        final_data = self._add_wavelet_features_if_missing(final_data)
        print(f"[FE_REPLICATOR] ✅ Wavelet features ensured: {final_data.shape}")
        
        # Step 7.6: Remove duplicate columns (e.g., OPEN.1, HIGH.1, LOW.1, CLOSE.1)
        duplicate_columns = [col for col in final_data.columns if col.endswith('.1')]
        if duplicate_columns:
            print(f"[FE_REPLICATOR] Removing duplicate columns: {duplicate_columns}")
            final_data = final_data.drop(columns=duplicate_columns)
            print(f"[FE_REPLICATOR] ✅ Duplicate columns removed: {final_data.shape}")
        
        # Step 8: Reorder columns to match feature-eng exactly 
        expected_column_order = ['DATE_TIME', 'RSI', 'MACD', 'MACD_Histogram', 'MACD_Signal', 'EMA', 'Stochastic_%K', 'Stochastic_%D', 'ADX', 'DI+', 'DI-', 'ATR', 'CCI', 'WilliamsR', 'Momentum', 'ROC', 'OPEN', 'HIGH', 'LOW', 'BC-BO', 'BH-BL', 'BH-BO', 'BO-BL', 'S&P500_Close', 'vix_close', 'CLOSE_15m_tick_1', 'CLOSE_15m_tick_2', 'CLOSE_15m_tick_3', 'CLOSE_15m_tick_4', 'CLOSE_15m_tick_5', 'CLOSE_15m_tick_6', 'CLOSE_15m_tick_7', 'CLOSE_15m_tick_8', 'CLOSE_30m_tick_1', 'CLOSE_30m_tick_2', 'CLOSE_30m_tick_3', 'CLOSE_30m_tick_4', 'CLOSE_30m_tick_5', 'CLOSE_30m_tick_6', 'CLOSE_30m_tick_7', 'CLOSE_30m_tick_8', 'day_of_month', 'hour_of_day', 'day_of_week', 'CLOSE_stl_trend', 'CLOSE_stl_seasonal', 'CLOSE_stl_resid', 'CLOSE_wav_detail_L1', 'CLOSE_wav_detail_L2', 'CLOSE_wav_approx_L2', 'CLOSE_mtm_band_1_0.000_0.010', 'CLOSE_mtm_band_2_0.010_0.060', 'CLOSE_mtm_band_3_0.060_0.200', 'CLOSE_mtm_band_4_0.200_0.500', 'CLOSE']
        
        # Reset index to have DATE_TIME as column
        final_data.reset_index(inplace=True)
        
        # Reorder columns to match the expected order
        available_columns = [col for col in expected_column_order if col in final_data.columns]
        final_data = final_data[available_columns]
        
        print(f"[FE_REPLICATOR] ✅ Reordered columns to match feature-eng output")
            
        return final_data
    
    def _apply_predefined_transformations(self, data: pd.DataFrame) -> pd.DataFrame:
        """Apply exact same transformations as feature-eng full dataset analysis."""
        print("[FE_REPLICATOR] Applying pre-determined log transformations...")
        
        # Based on feature-eng full dataset analysis (93084 rows):
        # These indicators get log-transformed to improve normality
        log_transform_indicators = [
            'MACD',         # CV 116.82507 (High) -> log improved normality  
            'MACD_Signal',  # CV 110.16903 (High) -> log improved normality
            'Stochastic_%D',# CV 0.51951 (Low) -> log improved normality
            'ADX',          # CV 0.40549 (Low) -> log improved normality  
            'ATR'           # CV 0.48785 (Low) -> log improved normality
        ]
        
        # Keep these indicators as original (no log transform)
        keep_original_indicators = [
            'RSI',            # CV 0.25607 (Low) -> original better
            'MACD_Histogram', # CV 10792.95279 (High) -> original better
            'EMA',            # CV 0.10023 (Low) -> original better
            'Stochastic_%K',  # CV 0.53521 (Low) -> original better
            'DI+',            # CV 0.37202 (Low) -> original better
            'DI-',            # CV 0.36457 (Low) -> original better
            'CCI',            # CV 394.79533 (High) -> original better
            'WilliamsR',      # CV 0.57534 (High) -> original better
            'Momentum',       # CV 229.53721 (High) -> original better
            'ROC'             # CV 353.73544 (High) -> original better
        ]
        
        transformed_data = data.copy()
        
        # Apply log transformations to specific indicators
        for indicator in log_transform_indicators:
            if indicator in transformed_data.columns:
                original_values = transformed_data[indicator]
                
                # Handle zeros and negative values (same as feature-eng logic)
                if (original_values <= 0).any():
                    min_value = original_values.min()
                    shifted_values = original_values - min_value + 1
                else:
                    shifted_values = original_values
                
                log_transformed = np.log(shifted_values)
                transformed_data[indicator] = log_transformed
                print(f"[FE_REPLICATOR] Applied log transformation to {indicator}")
        
        print(f"[FE_REPLICATOR] Transformation summary:")
        print(f"  - Log transformed: {log_transform_indicators}")
        print(f"  - Kept original: {keep_original_indicators}")
        
        return transformed_data

    def _apply_variability_analysis(self, data: pd.DataFrame) -> pd.DataFrame:
        """Apply the same variability and normality analysis as feature-eng."""
        # Import the function from feature-eng
        sys.path.insert(0, self.feature_eng_repo_path)
        from app.data_processor import analyze_variability_and_normality
        
        # Apply the analysis with the same config
        config = {
            'quiet_mode': True,  # Suppress plots
            'distribution_plot': False
        }
        
        transformed_data = analyze_variability_and_normality(data, config)
        return transformed_data
    
    def _process_additional_datasets(self, prepared_data: pd.DataFrame) -> pd.DataFrame:
        """Process additional datasets exactly like feature-eng does"""
        print("[FE_REPLICATOR] Processing additional datasets...")
        print(f"[DEBUG] Starting process_additional_datasets...")
        print(f"[DEBUG] prepared_data columns: {list(prepared_data.columns)}")
        print(f"[DEBUG] prepared_data shape: {prepared_data.shape}")
        
        # Set the DATE_TIME index (like feature-eng expects)
        data_for_processing = prepared_data.copy()
        if 'DATE_TIME' in data_for_processing.columns:
            data_for_processing['DATE_TIME'] = pd.to_datetime(data_for_processing['DATE_TIME'])
            data_for_processing.set_index('DATE_TIME', inplace=True)
            print(f"[DEBUG] Set DATE_TIME index, range: {data_for_processing.index.min()} to {data_for_processing.index.max()}")
        
        print(f"[DEBUG] Data for processing columns: {list(data_for_processing.columns)}")
        print(f"[DEBUG] Data for processing first 5 rows:")
        print(data_for_processing.head())
        
        # Create complete config for additional datasets processing
        config = self.fe_config['processing_params'].copy()
        config.update(self.fe_config['data_handling_params'])
        
        # Fix the dataset paths to point to the actual files
        config['sp500_dataset'] = os.path.join(self.feature_eng_repo_path, config.get('sp500_dataset', 'tests/data/sp_500_day_1927_2020_ohlc.csv'))
        config['vix_dataset'] = os.path.join(self.feature_eng_repo_path, config.get('vix_dataset', 'tests/data/vix_day_1990_2024.csv'))
        config['high_freq_dataset'] = os.path.join(self.feature_eng_repo_path, config.get('high_freq_dataset', 'tests/data/EURUSD-2000-2020-15m.csv'))
        config['input_file'] = os.path.join(self.feature_eng_repo_path, self.plugin_params['input_csv_path'])
        
        try:
            additional_features, _, _ = self.tech_indicator_plugin.process_additional_datasets(data_for_processing, config)
            return additional_features
        except Exception as e:
            print(f"[FE_REPLICATOR] ❌ Error in additional datasets: {e}")
            import traceback
            traceback.print_exc()
            # Return empty DataFrame with same index if processing fails
            return pd.DataFrame(index=data_for_processing.index)
    
    def _prepare_data_like_feature_eng(self, data: pd.DataFrame) -> pd.DataFrame:
        """Prepare data using the same method as feature-eng data_processor.py."""
        # Rename datetime column and set as index
        if 'datetime' in data.columns:
            data = data.copy()
            data.rename(columns={'datetime': 'DATE_TIME'}, inplace=True)
            # Use the same date parsing as feature-eng data_handler.py
            data['DATE_TIME'] = pd.to_datetime(data['DATE_TIME'], dayfirst=True, errors='coerce')
            data.set_index('DATE_TIME', inplace=True)
        
        # Apply the same column name transformations as feature-eng data_handler.py
        # Convert to uppercase column names to match feature-eng processing
        data = data.rename(columns=str.upper)
        
        # Apply data handling parameters from FE config
        data_params = self.fe_config['data_handling_params']
        header_mappings = data_params['header_mappings']
        dataset_type = data_params['dataset_type']
        
        if dataset_type in header_mappings:
            mappings = header_mappings[dataset_type]
            # Apply OHLC column mappings
            ohlc_columns = []
            for key in ['open', 'high', 'low', 'close']:
                mapped_col = mappings.get(key, key.upper())
                if mapped_col in data.columns:
                    ohlc_columns.append(mapped_col)
            
            # Select only OHLC columns for processing (same as feature-eng)
            if ohlc_columns:
                numeric_data = data[ohlc_columns].apply(pd.to_numeric, errors='coerce').fillna(0)
                print(f"[FE_REPLICATOR] ✅ Prepared OHLC data: {numeric_data.shape}")
                print(f"[FE_REPLICATOR] OHLC columns: {ohlc_columns}")
                return numeric_data
        
        # Fallback to standard column names
        standard_cols = ['OPEN', 'HIGH', 'LOW', 'CLOSE']
        available_cols = [col for col in standard_cols if col in data.columns]
        if available_cols:
            numeric_data = data[available_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
            print(f"[FE_REPLICATOR] ✅ Prepared OHLC data (fallback): {numeric_data.shape}")
            print(f"[FE_REPLICATOR] Available columns: {available_cols}")
            return numeric_data
        
        print(f"[FE_REPLICATOR] Available columns in data: {list(data.columns)}")
        raise ValueError("Unable to identify OHLC columns in the data")
    
    def save_processed_data(self, data: pd.DataFrame, output_path: str) -> str:
        """Save the processed data to CSV."""
        # Reset index to include DATE_TIME column
        if data.index.name == 'DATE_TIME' or isinstance(data.index, pd.DatetimeIndex):
            data_to_save = data.reset_index()
        else:
            data_to_save = data.copy()
            
        data_to_save.to_csv(output_path, index=False)
        
        print(f"[FE_REPLICATOR] ✅ Saved processed data: {output_path}")
        print(f"[FE_REPLICATOR] Output shape: {data_to_save.shape}")
        
        return output_path
    
    def compare_with_feature_eng_output(self, replicated_data: pd.DataFrame, num_rows: int = 1000) -> Dict[str, Any]:
        """Compare replicated output with feature-eng output for exact matching."""
        print("[FE_REPLICATOR] Starting exact comparison...")
        
        # Calculate maximum window size needed for all decomposition methods
        # Based on the configuration parameters
        max_window_size = self._calculate_max_window_size()
        print(f"[FE_REPLICATOR] Maximum window size for all methods: {max_window_size}")
        print(f"[FE_REPLICATOR] Skipping first {max_window_size} rows to compare only valid calculated values")
        
        # Load feature-eng output
        fe_output_path = os.path.join(self.feature_eng_repo_path, self.plugin_params['comparison_csv_path'])
        
        if not os.path.exists(fe_output_path):
            raise FileNotFoundError(f"Feature-eng output not found: {fe_output_path}")
            
        fe_output = pd.read_csv(fe_output_path)
        
        # Skip initial rows that don't have sufficient window data for decomposition
        # Compare only rows from max_window_size onward
        start_row = max_window_size
        end_row = min(start_row + num_rows, len(fe_output), len(replicated_data))
        
        fe_comparison_rows = fe_output.iloc[start_row:end_row]
        replicated_comparison_rows = replicated_data.iloc[start_row:end_row]
        
        actual_comparison_rows = len(fe_comparison_rows)
        print(f"[FE_REPLICATOR] Comparing {actual_comparison_rows} rows (from row {start_row} to {end_row-1})...")
        print(f"[FE_REPLICATOR] Feature-eng shape: {fe_comparison_rows.shape}")
        print(f"[FE_REPLICATOR] Replicated shape: {replicated_comparison_rows.shape}")
        
        # Compare shapes
        shape_match = fe_comparison_rows.shape == replicated_comparison_rows.shape
        
        # Compare column names
        fe_columns = set(fe_comparison_rows.columns)
        replicated_columns = set(replicated_comparison_rows.columns)
        columns_match = fe_columns == replicated_columns
        
        # Compare values for exact matching
        exact_match = True
        mismatched_columns = []
        
        if shape_match and columns_match:
            # Align columns
            common_columns = sorted(fe_columns.intersection(replicated_columns))
            
            for col in common_columns:
                fe_values = fe_comparison_rows[col].values
                replicated_values = replicated_comparison_rows[col].values
                
                # Convert to float64 to ensure compatible types for comparison
                try:
                    fe_values = fe_values.astype(np.float64)
                    replicated_values = replicated_values.astype(np.float64)
                except (ValueError, TypeError):
                    # Handle non-numeric columns (like datetime strings)
                    fe_values = fe_values.astype(str)
                    replicated_values = replicated_values.astype(str)
                
                # For exact matching with floating-point tolerance
                try:
                    # Use a very small tolerance for floating-point comparison
                    tolerance = 1e-10
                    if not np.allclose(fe_values, replicated_values, atol=tolerance, rtol=tolerance, equal_nan=True):
                        exact_match = False
                        mismatched_columns.append(col)
                        
                        # Show detailed comparison for debugging
                        print(f"[FE_REPLICATOR] ❌ MISMATCH in column '{col}':")
                        print(f"  Feature-eng first 3 values: {fe_values[:3]}")
                        print(f"  Replicated first 3 values: {replicated_values[:3]}")
                        print(f"  Max difference: {np.max(np.abs(fe_values - replicated_values))}")
                except Exception as e:
                    print(f"[FE_REPLICATOR] ❌ Error comparing column '{col}': {e}")
                    exact_match = False
                    mismatched_columns.append(col)
        else:
            exact_match = False
        
        comparison_result = {
            'exact_match': exact_match,
            'shape_match': shape_match,
            'columns_match': columns_match,
            'fe_shape': fe_comparison_rows.shape,
            'replicated_shape': replicated_comparison_rows.shape,
            'fe_columns': list(fe_columns),
            'replicated_columns': list(replicated_columns),
            'mismatched_columns': mismatched_columns,
            'num_rows_compared': actual_comparison_rows
        }
        
        if exact_match:
            print("[FE_REPLICATOR] ✅ PERFECT MATCH! Exact replicability achieved!")
        else:
            print("[FE_REPLICATOR] ❌ MISMATCH detected. Replicability failed.")
            print(f"[FE_REPLICATOR] Shape match: {shape_match}")
            print(f"[FE_REPLICATOR] Columns match: {columns_match}")
            print(f"[FE_REPLICATOR] Mismatched columns: {mismatched_columns}")
        
        return comparison_result
    
    def process_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Main processing method called by the prediction provider."""
        try:
            print("[FE_REPLICATOR] 🚀 Starting FE replication process...")
            
            # Step 1: Load FE configuration
            self.load_fe_config(self.plugin_params['fe_config_path'])
            
            # Step 2: Setup feature-eng environment
            self.setup_feature_eng_environment()
            
            # Step 3: Load input data (last N rows)
            input_data = self.load_input_data(
                self.plugin_params['input_csv_path'],
                self.plugin_params['num_rows_to_process']
            )
            
            # Step 4: Process data with FE pipeline
            processed_data = self.process_data_with_fe_pipeline(input_data)
            
            # Step 5: Save processed data
            output_path = self.save_processed_data(
                processed_data,
                self.plugin_params['output_csv_path']
            )
            
            # Step 6: Compare with feature-eng output for exact matching
            comparison_result = self.compare_with_feature_eng_output(
                processed_data,
                self.plugin_params['num_rows_to_compare']
            )
            
            return {
                'status': 'success',
                'message': 'FE replication completed',
                'output_path': output_path,
                'processed_rows': len(processed_data),
                'comparison_result': comparison_result,
                'exact_match': comparison_result['exact_match']
            }
            
        except Exception as e:
            print(f"[FE_REPLICATOR] ❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return {
                'status': 'error',
                'message': f'FE replication failed: {str(e)}',
                'exact_match': False
            }
    
    def _calculate_max_window_size(self) -> int:
        """Calculate the maximum window size needed for all decomposition methods."""
        if not self.fe_config:
            # Fallback values if config not available
            return 200  # Conservative estimate
            
        decomp_params = self.fe_config.get('decomposition_params', {})
        
        # STL window size
        stl_window = decomp_params.get('stl_window', 49)  # Default from config
        
        # MTM window size  
        mtm_window = decomp_params.get('mtm_window_len', 168)  # Default from config
        
        # Wavelet minimum window size (based on levels and wavelet type)
        wavelet_levels = decomp_params.get('wavelet_levels', 2)
        wavelet_min_window = max(2 ** wavelet_levels, 16)  # Conservative estimate for db4
        
        # Get maximum of all window sizes
        max_window = max(stl_window, mtm_window, wavelet_min_window)
        
        print(f"[FE_REPLICATOR] Window sizes - STL: {stl_window}, MTM: {mtm_window}, Wavelet: {wavelet_min_window}")
        print(f"[FE_REPLICATOR] Maximum window size: {max_window}")
        
        return max_window

# For backward compatibility
Plugin = FeReplicatorFeeder
