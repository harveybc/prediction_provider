#!/usr/bin/env python3
"""
Default Feeder Plugin

This plugin handles data fetching and feeding for the Prediction Provider.
It downloads and processes financial data from various sources based on configuration parameters.
Supports batch data fetching, date filtering, and feature selection.
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
import requests
import os
try:
    import pandas_ta as ta
except Exception:  # optional dependency
    ta = None

try:
    import yfinance as yf
except Exception:  # optional dependency
    yf = None

class DefaultFeeder:
    """
    Default data feeder plugin for fetching financial market data.
    """
    
    # Plugin parameters with default values
    plugin_params = {
        "data_source": "yfinance",  # 'yfinance' | 'file'
        "data_file_path": None,
        "date_column": "DATE_TIME",
        "feature_columns": None,
        "instrument": "MSFT",
        "correlated_instruments": [],
        "n_batches": 1,
        "batch_size": 256,
        "window_size": 256,
        "use_normalization_json": None,
        "target_column": "CLOSE",
    }
    
    def __init__(self, config=None):
        """
        Initialize the feeder plugin.
        
        Args:
            config (dict): Configuration parameters
        """
        self.params = self.plugin_params.copy()
        self.normalization_params = None
        self._file_df_cache = None
        
        if config:
            self.set_params(**config)

        if self.params.get("use_normalization_json"):
            self._load_normalization_params()

        if self.params.get("data_source") == "file" and self.params.get("data_file_path"):
            self._load_file_data()

    def _load_file_data(self):
        path = self.params.get("data_file_path")
        if not path:
            self._file_df_cache = None
            return

        if not os.path.exists(path):
            raise FileNotFoundError(f"data_file_path not found: {path}")

        date_col = self.params.get("date_column", "DATE_TIME")
        df = pd.read_csv(path)
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        self._file_df_cache = df

    def _load_normalization_params(self):
        path = self.params.get("use_normalization_json")
        if not path:
            self.normalization_params = {}
            return
            
        try:
            with open(path, 'r') as f:
                self.normalization_params = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load or parse normalization file at {path}. Error: {e}")
            self.normalization_params = {}

    def set_params(self, **kwargs):
        """
        Update plugin parameters with provided configuration.
        """
        for key, value in kwargs.items():
            self.params[key] = value
        if 'use_normalization_json' in kwargs:
            self._load_normalization_params()
        if 'data_file_path' in kwargs or 'data_source' in kwargs or 'date_column' in kwargs:
            if self.params.get("data_source") == "file" and self.params.get("data_file_path"):
                self._load_file_data()

    def _fetch_instrument_data(self, instrument, period="5d", interval="1h"):
        """Fetches historical data for a single instrument from yfinance."""
        if yf is None:
            raise ImportError("yfinance is required for data_source='yfinance'")
        ticker = yf.Ticker(instrument)
        hist = ticker.history(period=period, interval=interval)
        return hist

    def _calculate_features(self, df):
        """
        Calculate technical indicators and other features using pandas_ta.
        """
        if df is None or df.empty:
            return pd.DataFrame()

        if ta is None:
            raise ImportError("pandas_ta is required to calculate technical indicators")

        # Define a custom strategy to avoid indicators with deprecated pandas functions
        custom_strategy = ta.Strategy(
            name="Custom Strategy",
            description="A custom strategy to calculate required indicators",
            ta=[
                {"kind": "rsi"},
                {"kind": "macd", "fast": 12, "slow": 26, "signal": 9},
                {"kind": "ema", "length": 20},
                {"kind": "stoch", "k": 14, "d": 3, "smooth_k": 3},
                {"kind": "adx", "length": 14},
                {"kind": "atr", "length": 14},
                {"kind": "cci", "length": 14, "c": 0.015},
                {"kind": "willr", "length": 14},
                {"kind": "mom", "length": 10},
                {"kind": "roc", "length": 10},
            ]
        )
        # Apply the custom strategy
        df.ta.strategy(custom_strategy)

        # Bar-based features
        df['BC-BO'] = df['Close'].shift(1) - df['Open'].shift(1)
        df['BH-BL'] = df['High'].shift(1) - df['Low'].shift(1)
        df['BH-BO'] = df['High'].shift(1) - df['Open'].shift(1)
        df['BO-BL'] = df['Open'].shift(1) - df['Low'].shift(1)

        # Time-based features
        df['day_of_month'] = df.index.day
        df['hour_of_day'] = df.index.hour
        df['day_of_week'] = df.index.dayofweek

        return df

    def _normalize_data(self, df):
        """
        Normalize the dataframe using pre-loaded parameters.
        """
        if not self.normalization_params:
            print("Warning: Normalization parameters not loaded. Skipping normalization.")
            return df

        for col, params in self.normalization_params.items():
            if col in df.columns and 'min' in params and 'max' in params:
                col_min = params['min']
                col_max = params['max']
                if col_max > col_min:
                    df[col] = (df[col] - col_min) / (col_max - col_min)
        return df

    def fetch(self) -> pd.DataFrame:
        """Main method to fetch, process, and return data."""
        if self.params.get("data_source") == "file":
            if self._file_df_cache is None:
                self._load_file_data()
            df = self._file_df_cache.copy() if self._file_df_cache is not None else pd.DataFrame()
            return df.reset_index(drop=True)

        instrument = self.params.get("instrument", "EURUSD=X")
        num_records = self.params.get("n_batches", 1) * self.params.get("batch_size", 256)

        # Fetch main instrument data (OHLC)
        df = self._fetch_instrument_data(instrument, period="1mo", interval="1h") # Fetch more to ensure enough data

        # Fetch correlated instruments
        correlated_instruments = self.params.get("correlated_instruments", [])
        for inst in correlated_instruments:
            corr_df = self._fetch_instrument_data(inst, period="1mo", interval="1h")
            df = pd.merge(df, corr_df[['Close']].rename(columns={'Close': f'{inst}_Close'}), left_index=True, right_index=True, how='left')

        df = df.ffill()

        # Calculate features
        df = self._calculate_features(df)

        df = df.dropna().reset_index(drop=False)
        df.rename(columns={'index': 'DATE_TIME'}, inplace=True)

        # Normalize data
        df = self._normalize_data(df)

        # Adjust column names from pandas_ta
        df.rename(columns={
            'MACD_12_26_9': 'MACD',
            'MACDh_12_26_9': 'MACD_Histogram',
            'MACDs_12_26_9': 'MACD_Signal',
            'EMA_20': 'EMA',
            'STOCHk_14_3_3': 'Stochastic_%K',
            'STOCHd_14_3_3': 'Stochastic_%D',
            'ADX_14': 'ADX',
            'DMP_14': 'DI+',
            'DMN_14': 'DI-',
            'ATR_14': 'ATR',
            'CCI_14_0.015': 'CCI',
            'WILLR_14': 'WilliamsR',
            'MOM_10': 'Momentum',
            'ROC_10': 'ROC',
            'Open': 'OPEN',
            'High': 'HIGH',
            'Low': 'LOW',
            'Close': 'CLOSE',
            '^GSPC_Close': 'S&P500_Close',
            '^VIX_Close': 'vix_close'
        }, inplace=True)

        final_cols = [
            'DATE_TIME','RSI','MACD','MACD_Histogram','MACD_Signal','EMA','Stochastic_%K','Stochastic_%D','ADX','DI+','DI-','ATR','CCI','WilliamsR','Momentum','ROC','OPEN','HIGH','LOW','CLOSE','BC-BO','BH-BL','BH-BO','BO-BL','S&P500_Close','vix_close','CLOSE_15m_tick_1','CLOSE_15m_tick_2','CLOSE_15m_tick_3','CLOSE_15m_tick_4','CLOSE_15m_tick_5','CLOSE_15m_tick_6','CLOSE_15m_tick_7','CLOSE_15m_tick_8','CLOSE_30m_tick_1','CLOSE_30m_tick_2','CLOSE_30m_tick_3','CLOSE_30m_tick_4','CLOSE_30m_tick_5','CLOSE_30m_tick_6','CLOSE_30m_tick_7','CLOSE_30m_tick_8','day_of_month','hour_of_day','day_of_week'
        ]

        # Fill missing required columns with 0
        for col in final_cols:
            if col not in df.columns:
                df[col] = 0
        
        df = df[final_cols]

        return df.tail(self.params.get("window_size"))

    def fetch_data_sync(self, ticker, start_date, end_date):
        """
        Synchronous method to fetch data for a given ticker and date range.
        This method is used by the unit tests.
        """
        try:
            import yfinance as yf
            data = yf.download(ticker, start=start_date, end=end_date)
            return data
        except Exception as e:
            # Re-raise the exception to allow tests to catch it
            raise e
