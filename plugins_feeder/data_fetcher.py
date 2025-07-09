#!/usr/bin/env python3
"""
Data Fetcher Module

Handles all external data fetching operations from Yahoo Finance API.
Responsible for efficiently fetching multi-timeframe market data.
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

class DataFetcher:
    """
    Handles all external data fetching operations.
    Efficiently fetches multi-timeframe data with minimal API calls.
    """
    
    def __init__(self):
        """Initialize the data fetcher."""
        # Symbol mappings for Yahoo Finance
        self.symbols = {
            'eurusd': 'EURUSD=X',
            'sp500': '^GSPC',
            'vix': '^VIX'
        }
    
    def fetch_all_timeframes(self, start_date: datetime, end_date: datetime) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Efficiently fetch all required timeframes in minimal API calls.
        
        Args:
            start_date: Start datetime
            end_date: End datetime
            
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
