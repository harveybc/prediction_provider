#!/usr/bin/env python3
"""
Real Market Data Feeder Plugin

Efficiently fetches real EURUSD, S&P500, and VIX data with multi-timeframe support.
Optimized to minimize API calls while providing all required timeframes.
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import json
import logging
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)

class RealFeederPlugin:
    """
    Real market data feeder plugin with multi-timeframe support.
    
    This feeder efficiently fetches:
    - EURUSD hourly HLOC data
    - S&P500 hourly close data  
    - VIX hourly close data
    - 15-minute ticks (last 8 before each hour)
    - 30-minute ticks (last 8 before each hour)
    """
    
    # Plugin parameters with default values
    plugin_params = {
        "instrument": "EURUSD=X",
        "correlated_instruments": ["^GSPC", "^VIX"],
        "n_batches": 1,
        "batch_size": 256,
        "window_size": 256,
        "use_normalization_json": "examples/data/phase_3/phase_3_debug_out.json",
        "target_column": "CLOSE",
        "additional_previous_ticks": 50,  # Extra ticks for technical indicators
        "error_tolerance": 0.001  # Tolerance for validation against historical data
    }
    
    def __init__(self, config=None):
        """Initialize the real feeder plugin."""
        self.params = self.plugin_params.copy()
        self.normalization_params = None
        
        if config:
            self.set_params(**config)
        
        # Load normalization parameters
        if self.params.get("use_normalization_json"):
            self._load_normalization_params()
        
        # Symbol mappings for Yahoo Finance
        self.symbols = {
            'eurusd': 'EURUSD=X',
            'sp500': '^GSPC',
            'vix': '^VIX'
        }
    
    def set_params(self, **kwargs):
        """Update plugin parameters."""
        for key, value in kwargs.items():
            self.params[key] = value
        if 'use_normalization_json' in kwargs:
            self._load_normalization_params()
    
    def _load_normalization_params(self):
        """Load normalization min/max values from JSON file."""
        path = self.params["use_normalization_json"]
        try:
            with open(path, 'r') as f:
                self.normalization_params = json.load(f)
            logger.info(f"Loaded normalization parameters from {path}")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Could not load normalization file at {path}: {e}")
            self.normalization_params = {}
    
    def fetch(self) -> pd.DataFrame:
        """Main fetch method called by pipeline (for compatibility)."""
        # For compatibility with existing pipeline, fetch recent data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)  # Enough for indicators
        
        return self.fetch_data_for_period(
            start_date=start_date.strftime('%Y-%m-%d %H:%M:%S'),
            end_date=end_date.strftime('%Y-%m-%d %H:%M:%S')
        )
    
    def fetch_data_for_period(self, start_date: str, end_date: str, 
                            additional_previous_ticks: Optional[int] = None) -> pd.DataFrame:
        """
        Fetch data for a specific period with multi-timeframe support.
        
        Args:
            start_date: Start datetime string (YYYY-MM-DD HH:MM:SS)
            end_date: End datetime string (YYYY-MM-DD HH:MM:SS) 
            additional_previous_ticks: Extra ticks for technical indicators
            
        Returns:
            DataFrame with all columns (excluding technical indicators)
        """
        try:
            # Parse dates
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            
            # Add buffer for technical indicators
            buffer_ticks = additional_previous_ticks or self.params["additional_previous_ticks"]
            extended_start = start_dt - timedelta(hours=buffer_ticks)
            
            logger.info(f"Fetching data from {extended_start} to {end_dt}")
            logger.info(f"Target period: {start_dt} to {end_dt}")
            
            # Step 1: Fetch all required timeframes efficiently
            hourly_data, data_15m, data_30m = self._fetch_all_timeframes(
                extended_start, end_dt
            )
            
            # Step 2: Build the complete dataset for target period
            target_hourly = hourly_data[
                (hourly_data.index >= start_dt) & (hourly_data.index <= end_dt)
            ].copy()
            
            if target_hourly.empty:
                raise ValueError(f"No data found for target period {start_dt} to {end_dt}")
            
            # Step 3: Generate all columns (except technical indicators)
            result = self._generate_all_columns(target_hourly, data_15m, data_30m)
            
            # Step 4: Apply normalization
            result = self._apply_normalization(result)
            
            logger.info(f"Generated dataset with {len(result)} rows and {len(result.columns)} columns")
            return result
            
        except Exception as e:
            logger.error(f"Error fetching data for period: {e}")
            raise
    
    def _fetch_all_timeframes(self, start_date: datetime, end_date: datetime) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Efficiently fetch all required timeframes in minimal API calls.
        
        Returns:
            Tuple of (hourly_data, data_15m, data_30m)
        """
        try:
            # Fetch hourly data for all symbols
            hourly_data = self._fetch_hourly_data(start_date, end_date)
            
            # Fetch 15-minute data (only EURUSD needed for ticks)
            data_15m = self._fetch_15min_data(start_date, end_date)
            
            # Fetch 30-minute data (only EURUSD needed for ticks)
            data_30m = self._fetch_30min_data(start_date, end_date)
            
            return hourly_data, data_15m, data_30m
            
        except Exception as e:
            logger.error(f"Error fetching timeframe data: {e}")
            raise
    
    def _fetch_hourly_data(self, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Fetch hourly HLOC data for EURUSD, S&P500, and VIX."""
        
        combined_data = pd.DataFrame()
        
        for name, symbol in self.symbols.items():
            logger.info(f"Fetching hourly {name} data ({symbol})...")
            
            ticker = yf.Ticker(symbol)
            data = ticker.history(
                start=start_date.strftime('%Y-%m-%d'),
                end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                interval='1h',
                auto_adjust=True,
                prepost=True
            )
            
            if data.empty:
                logger.warning(f"No hourly data for {name}")
                continue
            
            # Remove timezone info for comparison if present
            if data.index.tz is not None:
                data.index = data.index.tz_localize(None)
            
            # Ensure start_date and end_date are timezone-naive
            start_date_naive = start_date.replace(tzinfo=None) if start_date.tzinfo else start_date
            end_date_naive = end_date.replace(tzinfo=None) if end_date.tzinfo else end_date
            
            # Filter to exact time range
            data = data[(data.index >= start_date_naive) & (data.index <= end_date_naive)]
            
            if name == 'eurusd':
                # For EURUSD, keep HLOC
                data = data.rename(columns={
                    'Open': 'OPEN',
                    'High': 'HIGH', 
                    'Low': 'LOW',
                    'Close': 'CLOSE'
                })
                combined_data = data[['OPEN', 'HIGH', 'LOW', 'CLOSE']].copy()
            else:
                # For S&P500 and VIX, only keep Close
                close_col = 'S&P500_Close' if name == 'sp500' else 'vix_close'
                if combined_data.empty:
                    combined_data = pd.DataFrame(index=data.index)
                
                combined_data = combined_data.join(
                    data[['Close']].rename(columns={'Close': close_col}),
                    how='outer'
                )
        
        # Forward fill missing values and drop NaN
        combined_data = combined_data.ffill().dropna()
        
        logger.info(f"Hourly data shape: {combined_data.shape}")
        return combined_data
    
    def _fetch_15min_data(self, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Fetch 15-minute EURUSD data for tick calculations."""
        
        logger.info("Fetching 15-minute EURUSD data...")
        
        ticker = yf.Ticker(self.symbols['eurusd'])
        data = ticker.history(
            start=start_date.strftime('%Y-%m-%d'),
            end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
            interval='15m',
            auto_adjust=True,
            prepost=True
        )
        
        if data.empty:
            logger.warning("No 15-minute data available")
            return pd.DataFrame()
        
        # Remove timezone info for comparison if present
        if data.index.tz is not None:
            data.index = data.index.tz_localize(None)
        
        # Ensure start_date and end_date are timezone-naive
        start_date_naive = start_date.replace(tzinfo=None) if start_date.tzinfo else start_date
        end_date_naive = end_date.replace(tzinfo=None) if end_date.tzinfo else end_date
        
        # Filter to time range and keep only Close
        data = data[(data.index >= start_date_naive) & (data.index <= end_date_naive)]
        
        logger.info(f"15-minute data shape: {data.shape}")
        return data[['Close']].rename(columns={'Close': 'CLOSE_15m'})
    
    def _fetch_30min_data(self, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Fetch 30-minute EURUSD data for tick calculations."""
        
        logger.info("Fetching 30-minute EURUSD data...")
        
        ticker = yf.Ticker(self.symbols['eurusd'])
        data = ticker.history(
            start=start_date.strftime('%Y-%m-%d'),
            end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
            interval='30m',
            auto_adjust=True,
            prepost=True
        )
        
        if data.empty:
            logger.warning("No 30-minute data available")
            return pd.DataFrame()
        
        # Remove timezone info for comparison if present
        if data.index.tz is not None:
            data.index = data.index.tz_localize(None)
        
        # Ensure start_date and end_date are timezone-naive
        start_date_naive = start_date.replace(tzinfo=None) if start_date.tzinfo else start_date
        end_date_naive = end_date.replace(tzinfo=None) if end_date.tzinfo else end_date
        
        # Filter to time range and keep only Close
        data = data[(data.index >= start_date_naive) & (data.index <= end_date_naive)]
        
        logger.info(f"30-minute data shape: {data.shape}")
        return data[['Close']].rename(columns={'Close': 'CLOSE_30m'})
    
    def _generate_all_columns(self, hourly_data: pd.DataFrame, 
                            data_15m: pd.DataFrame, data_30m: pd.DataFrame) -> pd.DataFrame:
        """
        Generate all required columns (except technical indicators).
        
        Returns DataFrame with columns:
        DATE_TIME, OPEN, HIGH, LOW, CLOSE, BC-BO, BH-BL, BH-BO, BO-BL,
        S&P500_Close, vix_close, CLOSE_15m_tick_1-8, CLOSE_30m_tick_1-8,
        day_of_month, hour_of_day, day_of_week
        """
        
        result = hourly_data.copy()
        
        # Reset index to make datetime a column
        result.reset_index(inplace=True)
        if 'Datetime' in result.columns:
            result.rename(columns={'Datetime': 'DATE_TIME'}, inplace=True)
        elif result.index.name is not None:
            result['DATE_TIME'] = result.index
        
        # Calculate price relationships (Bar Characteristics)
        result['BC-BO'] = result['CLOSE'] - result['OPEN']  # Body Close - Body Open
        result['BH-BL'] = result['HIGH'] - result['LOW']    # Body High - Body Low  
        result['BH-BO'] = result['HIGH'] - result['OPEN']   # Body High - Body Open
        result['BO-BL'] = result['OPEN'] - result['LOW']    # Body Open - Body Low
        
        # Calculate multi-timeframe tick data
        result = self._calculate_15m_ticks(result, data_15m)
        result = self._calculate_30m_ticks(result, data_30m)
        
        # Calculate time features
        result['day_of_month'] = pd.to_datetime(result['DATE_TIME']).dt.day
        result['hour_of_day'] = pd.to_datetime(result['DATE_TIME']).dt.hour
        result['day_of_week'] = pd.to_datetime(result['DATE_TIME']).dt.dayofweek
        
        # Ensure required columns exist (fill missing with zeros)
        required_columns = [
            'DATE_TIME', 'OPEN', 'HIGH', 'LOW', 'CLOSE',
            'BC-BO', 'BH-BL', 'BH-BO', 'BO-BL', 'S&P500_Close', 'vix_close',
            'CLOSE_15m_tick_1', 'CLOSE_15m_tick_2', 'CLOSE_15m_tick_3', 'CLOSE_15m_tick_4',
            'CLOSE_15m_tick_5', 'CLOSE_15m_tick_6', 'CLOSE_15m_tick_7', 'CLOSE_15m_tick_8',
            'CLOSE_30m_tick_1', 'CLOSE_30m_tick_2', 'CLOSE_30m_tick_3', 'CLOSE_30m_tick_4',
            'CLOSE_30m_tick_5', 'CLOSE_30m_tick_6', 'CLOSE_30m_tick_7', 'CLOSE_30m_tick_8',
            'day_of_month', 'hour_of_day', 'day_of_week'
        ]
        
        for col in required_columns:
            if col not in result.columns:
                logger.warning(f"Missing column {col}, filling with zeros")
                result[col] = 0.0
        
        # Select and order columns
        result = result[required_columns]
        
        logger.info(f"Generated {len(required_columns)} non-technical-indicator columns")
        return result
    
    def _calculate_15m_ticks(self, hourly_data: pd.DataFrame, data_15m: pd.DataFrame) -> pd.DataFrame:
        """Calculate the last 8 15-minute ticks before each hour."""
        
        if data_15m.empty:
            logger.warning("No 15-minute data available, filling ticks with hourly close")
            for i in range(1, 9):
                hourly_data[f'CLOSE_15m_tick_{i}'] = hourly_data['CLOSE']
            return hourly_data
        
        # For each hour, find the last 8 15-minute closes before that hour
        for idx, row in hourly_data.iterrows():
            hour_time = pd.to_datetime(row['DATE_TIME'])
            
            # Find 15-minute data before this hour
            mask = data_15m.index < hour_time
            recent_15m = data_15m[mask].tail(8)
            
            # Fill tick columns (tick_1 is most recent, tick_8 is oldest)
            for i in range(1, 9):
                tick_idx = -(i)  # Start from most recent
                if len(recent_15m) >= i:
                    hourly_data.loc[idx, f'CLOSE_15m_tick_{i}'] = recent_15m.iloc[tick_idx]['CLOSE_15m']
                else:
                    # If not enough historical data, use hourly close
                    hourly_data.loc[idx, f'CLOSE_15m_tick_{i}'] = row['CLOSE']
        
        return hourly_data
    
    def _calculate_30m_ticks(self, hourly_data: pd.DataFrame, data_30m: pd.DataFrame) -> pd.DataFrame:
        """Calculate the last 8 30-minute ticks before each hour."""
        
        if data_30m.empty:
            logger.warning("No 30-minute data available, filling ticks with hourly close")
            for i in range(1, 9):
                hourly_data[f'CLOSE_30m_tick_{i}'] = hourly_data['CLOSE']
            return hourly_data
        
        # For each hour, find the last 8 30-minute closes before that hour
        for idx, row in hourly_data.iterrows():
            hour_time = pd.to_datetime(row['DATE_TIME'])
            
            # Find 30-minute data before this hour
            mask = data_30m.index < hour_time
            recent_30m = data_30m[mask].tail(8)
            
            # Fill tick columns (tick_1 is most recent, tick_8 is oldest)
            for i in range(1, 9):
                tick_idx = -(i)  # Start from most recent
                if len(recent_30m) >= i:
                    hourly_data.loc[idx, f'CLOSE_30m_tick_{i}'] = recent_30m.iloc[tick_idx]['CLOSE_30m']
                else:
                    # If not enough historical data, use hourly close
                    hourly_data.loc[idx, f'CLOSE_30m_tick_{i}'] = row['CLOSE']
        
        return hourly_data
    
    def _apply_normalization(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply min-max normalization using training data ranges."""
        
        if not self.normalization_params:
            logger.warning("No normalization parameters available, skipping normalization")
            return df
        
        df_normalized = df.copy()
        
        for column in df.columns:
            if column == 'DATE_TIME':
                continue  # Skip datetime column
            
            if column in self.normalization_params:
                min_val = self.normalization_params[column]['min']
                max_val = self.normalization_params[column]['max']
                
                # Apply min-max normalization: (x - min) / (max - min)
                if max_val != min_val:  # Avoid division by zero
                    df_normalized[column] = (df[column] - min_val) / (max_val - min_val)
                else:
                    logger.warning(f"Column {column} has min=max, setting to 0")
                    df_normalized[column] = 0.0
                
                logger.debug(f"Normalized {column}: range [{min_val}, {max_val}]")
            else:
                logger.warning(f"No normalization values for column {column}")
        
        return df_normalized
    
    def validate_against_historical(self, generated_data: pd.DataFrame, 
                                  historical_csv: str = "examples/data/phase_3/normalized_d4.csv") -> Dict[str, Any]:
        """
        Validate generated data against historical data.
        
        Args:
            generated_data: Generated dataset
            historical_csv: Path to historical CSV for comparison
            
        Returns:
            Dictionary with validation results
        """
        try:
            # Load historical data
            historical_data = pd.read_csv(historical_csv)
            logger.info(f"Loaded historical data: {historical_data.shape}")
            
            # Find overlapping date range
            generated_dates = pd.to_datetime(generated_data['DATE_TIME'])
            historical_dates = pd.to_datetime(historical_data['DATE_TIME'])
            
            # Find common dates
            common_dates = set(generated_dates.dt.strftime('%Y-%m-%d %H:%M:%S')).intersection(
                set(historical_dates.dt.strftime('%Y-%m-%d %H:%M:%S'))
            )
            
            if not common_dates:
                return {
                    'validation_passed': False,
                    'error': 'No overlapping dates found between generated and historical data',
                    'generated_date_range': f"{generated_dates.min()} to {generated_dates.max()}",
                    'historical_date_range': f"{historical_dates.min()} to {historical_dates.max()}"
                }
            
            logger.info(f"Found {len(common_dates)} overlapping dates for validation")
            
            # Compare overlapping data
            validation_results = {
                'validation_passed': True,
                'total_common_dates': len(common_dates),
                'column_comparisons': {},
                'tolerance': self.params['error_tolerance']
            }
            
            # Get non-technical indicator columns for comparison
            comparable_columns = [
                'OPEN', 'HIGH', 'LOW', 'CLOSE', 'BC-BO', 'BH-BL', 'BH-BO', 'BO-BL',
                'S&P500_Close', 'vix_close', 'day_of_month', 'hour_of_day', 'day_of_week'
            ]
            
            for col in comparable_columns:
                if col in generated_data.columns and col in historical_data.columns:
                    # Compare values for common dates
                    gen_subset = generated_data[generated_data['DATE_TIME'].isin(common_dates)]
                    hist_subset = historical_data[historical_data['DATE_TIME'].isin(common_dates)]
                    
                    if len(gen_subset) > 0 and len(hist_subset) > 0:
                        # Calculate differences
                        differences = np.abs(gen_subset[col].values - hist_subset[col].values)
                        max_diff = np.max(differences)
                        mean_diff = np.mean(differences)
                        
                        validation_results['column_comparisons'][col] = {
                            'max_difference': float(max_diff),
                            'mean_difference': float(mean_diff),
                            'within_tolerance': max_diff <= self.params['error_tolerance']
                        }
                        
                        if max_diff > self.params['error_tolerance']:
                            validation_results['validation_passed'] = False
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return {
                'validation_passed': False,
                'error': str(e)
            }
    
    def fetch_data_sync(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Compatibility method for existing interfaces."""
        return self.fetch_data_for_period(start_date, end_date)
    
    def calculate_technical_indicators(self, data):
        """
        Calculate technical indicators matching the feature-eng plugin exactly.
        This replicates the exact logic from feature-eng/app/plugins/tech_indicator.py
        
        Args:
            data: DataFrame with OHLC columns
            
        Returns:
            DataFrame with calculated technical indicators
        """
        # Ensure we have the required OHLC columns (adjust for our naming convention)
        ohlc_mapping = {
            'OPEN': 'Open',
            'HIGH': 'High', 
            'LOW': 'Low',
            'CLOSE': 'Close'
        }
        
        # Create a copy with renamed columns for pandas_ta
        ohlc_data = data.copy()
        for old_name, new_name in ohlc_mapping.items():
            if old_name in ohlc_data.columns:
                ohlc_data[new_name] = ohlc_data[old_name]
        
        # Verify required columns exist
        required_cols = ['Open', 'High', 'Low', 'Close']
        for col in required_cols:
            if col not in ohlc_data.columns:
                raise ValueError(f"Missing required column: {col}")
        
        indicators = {}
        
        # Use pandas_ta for exact same calculations as feature-eng
        try:
            import pandas_ta as ta
            
            # List of indicators from feature-eng plugin_params
            indicator_list = ['rsi', 'macd', 'ema', 'stoch', 'adx', 'atr', 'cci', 'bbands', 'williams', 'momentum', 'roc']
            
            logger.info("Calculating technical indicators...")
            
            for indicator in indicator_list:
                logger.debug(f"Processing indicator: {indicator}")
                
                if indicator == 'rsi':
                    rsi = ta.rsi(ohlc_data['Close'])  # Default length is 14
                    if rsi is not None:
                        indicators['RSI'] = rsi
                
                elif indicator == 'macd':
                    macd = ta.macd(ohlc_data['Close'])  # Default fast=12, slow=26, signal=9
                    if 'MACD_12_26_9' in macd.columns:
                        indicators['MACD'] = macd['MACD_12_26_9']
                    if 'MACDh_12_26_9' in macd.columns:
                        indicators['MACD_Histogram'] = macd['MACDh_12_26_9']
                    if 'MACDs_12_26_9' in macd.columns:
                        indicators['MACD_Signal'] = macd['MACDs_12_26_9']
                
                elif indicator == 'ema':
                    ema = ta.ema(ohlc_data['Close'])  # Default length is 20
                    if ema is not None:
                        indicators['EMA'] = ema
                
                elif indicator == 'stoch':
                    stoch = ta.stoch(ohlc_data['High'], ohlc_data['Low'], ohlc_data['Close'])  # Default %K=14, %D=3, smooth_k=3
                    if 'STOCHk_14_3_3' in stoch.columns:
                        indicators['Stochastic_%K'] = stoch['STOCHk_14_3_3']
                    if 'STOCHd_14_3_3' in stoch.columns:
                        indicators['Stochastic_%D'] = stoch['STOCHd_14_3_3']
                
                elif indicator == 'adx':
                    adx = ta.adx(ohlc_data['High'], ohlc_data['Low'], ohlc_data['Close'])  # Default length is 14
                    if 'ADX_14' in adx.columns:
                        indicators['ADX'] = adx['ADX_14']
                    if 'DMP_14' in adx.columns:
                        indicators['DI+'] = adx['DMP_14']
                    if 'DMN_14' in adx.columns:
                        indicators['DI-'] = adx['DMN_14']
                
                elif indicator == 'atr':
                    atr = ta.atr(ohlc_data['High'], ohlc_data['Low'], ohlc_data['Close'])  # Default length is 14
                    if atr is not None:
                        indicators['ATR'] = atr
                
                elif indicator == 'cci':
                    cci = ta.cci(ohlc_data['High'], ohlc_data['Low'], ohlc_data['Close'])  # Default length is 20
                    if cci is not None:
                        indicators['CCI'] = cci
                
                elif indicator == 'bbands':
                    bbands = ta.bbands(ohlc_data['Close'])  # Default length=20, std=2.0
                    if 'BBU_20_2.0' in bbands.columns:
                        indicators['BB_Upper'] = bbands['BBU_20_2.0']
                    if 'BBM_20_2.0' in bbands.columns:
                        indicators['BB_Middle'] = bbands['BBM_20_2.0']
                    if 'BBL_20_2.0' in bbands.columns:
                        indicators['BB_Lower'] = bbands['BBL_20_2.0']
                
                elif indicator == 'williams':
                    williams = ta.willr(ohlc_data['High'], ohlc_data['Low'], ohlc_data['Close'])  # Default length is 14
                    if williams is not None:
                        indicators['WilliamsR'] = williams
                
                elif indicator == 'momentum':
                    momentum = ta.mom(ohlc_data['Close'])  # Default length is 10
                    if momentum is not None:
                        indicators['Momentum'] = momentum
                
                elif indicator == 'roc':
                    roc = ta.roc(ohlc_data['Close'])  # Default length is 10
                    if roc is not None:
                        indicators['ROC'] = roc
            
            # Additional features from feature-eng (calculated in process_additional_datasets)
            # These are calculated from the hourly dataset columns
            if 'HIGH' in data.columns and 'LOW' in data.columns:
                indicators['BH-BL'] = data['HIGH'] - data['LOW']
            if 'HIGH' in data.columns and 'OPEN' in data.columns:
                indicators['BH-BO'] = data['HIGH'] - data['OPEN']
            if 'OPEN' in data.columns and 'LOW' in data.columns:
                indicators['BO-BL'] = data['OPEN'] - data['LOW']
            
            # Seasonality columns (added when seasonality_columns=True in config)
            if hasattr(data.index, 'day'):
                indicators['day_of_month'] = data.index.day
                indicators['hour_of_day'] = data.index.hour  
                indicators['day_of_week'] = data.index.dayofweek
            
            logger.info(f"Calculated {len(indicators)} technical indicators")
            
        except ImportError:
            logger.warning("pandas_ta not available, skipping technical indicators")
            return pd.DataFrame(index=data.index)
        except Exception as e:
            logger.error(f"Error calculating technical indicators: {e}")
            return pd.DataFrame(index=data.index)
        
        # Create DataFrame from indicators
        indicator_df = pd.DataFrame(indicators, index=data.index)
        
        return indicator_df

    def generate_complete_features(self, start_date: str, end_date: str, additional_previous_ticks: int = None):
        """
        Generate complete feature set including technical indicators.
        
        Args:
            start_date: Start date in 'YYYY-MM-DD HH:MM:SS' format
            end_date: End date in 'YYYY-MM-DD HH:MM:SS' format
            additional_previous_ticks: Extra ticks for technical indicators
            
        Returns:
            DataFrame with all columns including technical indicators
        """
        try:
            # Calculate required buffer for technical indicators
            buffer_ticks = additional_previous_ticks or self.params["additional_previous_ticks"]
            extended_start = pd.to_datetime(start_date) - timedelta(hours=buffer_ticks)
            
            # Fetch extended data for technical indicators calculation
            logger.info(f"Fetching extended data from {extended_start} for technical indicators")
            extended_features = self.fetch_data_for_period(
                extended_start.strftime('%Y-%m-%d %H:%M:%S'), 
                end_date, 
                0  # No additional buffer since we already extended
            )
            
            if extended_features.empty:
                raise ValueError("No extended features data available")
            
            # Calculate technical indicators on extended data
            tech_indicators = self.calculate_technical_indicators(extended_features)
            
            # Get base features for target period only
            base_features = self.fetch_data_for_period(start_date, end_date, 0)
            
            # Align technical indicators with target period
            target_start = pd.to_datetime(start_date)
            target_end = pd.to_datetime(end_date)
            tech_indicators_aligned = tech_indicators[
                (tech_indicators.index >= target_start) & (tech_indicators.index <= target_end)
            ]
            
            # Combine base features with technical indicators
            result = base_features.copy()
            for col in tech_indicators_aligned.columns:
                if col not in result.columns:
                    result[col] = tech_indicators_aligned[col]
            
            # Apply normalization to the complete dataset
            result = self._apply_normalization(result)
            
            logger.info(f"Generated complete features with {len(result)} rows and {len(result.columns)} columns")
            logger.info(f"Technical indicators: {list(tech_indicators_aligned.columns)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating complete features: {e}")
            raise
