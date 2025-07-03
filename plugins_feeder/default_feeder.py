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
import pandas_ta as ta
import yfinance as yf

class DefaultFeederPlugin:
    """
    Default data feeder plugin for fetching financial market data.
    """
    
    # Plugin parameters with default values
    plugin_params = {
        "instrument": "EURUSD=X",
        "correlated_instruments": ["^GSPC", "^VIX"],
        "n_batches": 1,
        "batch_size": 256,
        "window_size": 256,
        "use_normalization_json": None,
        "target_column": "Close",
    }
    
    def __init__(self, config=None):
        """
        Initialize the feeder plugin.
        
        Args:
            config (dict): Configuration parameters
        """
        self.params = self.plugin_params.copy()
        self.normalization_params = None
        
        if config:
            self.set_params(**config)

        if self.params.get("use_normalization_json"):
            self._load_normalization_params()

    def _load_normalization_params(self):
        path = self.params["use_normalization_json"]
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

    def _fetch_instrument_data(self, instrument, period="5d", interval="1h"):
        """Fetches historical data for a single instrument from yfinance."""
        ticker = yf.Ticker(instrument)
        hist = ticker.history(period=period, interval=interval)
        return hist

    def _calculate_features(self, df):
        """
        Calculate technical indicators and other features using pandas_ta.
        """
        if df is None or df.empty:
            return pd.DataFrame()

        # Add all ta indicators
        df.ta.strategy("all")

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

        # High-frequency features (mocked for now, yfinance doesn't provide tick data)
        for i in range(1, 9):
            df[f'CLOSE_15m_tick_{i}'] = df['Close'].shift(i * 15, freq='T').ffill()
            df[f'CLOSE_30m_tick_{i}'] = df['Close'].shift(i * 30, freq='T').ffill()

        df = df.dropna().reset_index(drop=False)
        df.rename(columns={'index': 'DATE_TIME'}, inplace=True)

        # Normalize data
        df = self._normalize_data(df)

        # Ensure correct column order as per REFERENCE.md
        required_columns = [
            'DATE_TIME','RSI','MACD_12_26_9','MACDh_12_26_9','MACDs_12_26_9','EMA_20','STOCHk_14_3_3','STOCHd_14_3_3','ADX_14','DMP_14','DMN_14','ATR_14','CCI_14_0.015','WILLR_14','MOM_10','ROC_10','Open','High','Low','Close','BC-BO','BH-BL','BH-BO','BO-BL','^GSPC_Close','^VIX_Close','CLOSE_15m_tick_1','CLOSE_15m_tick_2','CLOSE_15m_tick_3','CLOSE_15m_tick_4','CLOSE_15m_tick_5','CLOSE_15m_tick_6','CLOSE_15m_tick_7','CLOSE_15m_tick_8','CLOSE_30m_tick_1','CLOSE_30m_tick_2','CLOSE_30m_tick_3','CLOSE_30m_tick_4','CLOSE_30m_tick_5','CLOSE_30m_tick_6','CLOSE_30m_tick_7','CLOSE_30m_tick_8','day_of_month','hour_of_day','day_of_week'
        ]

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
