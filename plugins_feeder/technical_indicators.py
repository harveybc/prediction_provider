#!/usr/bin/env python3
"""
Technical Indicators Calculator Module

This module provides exact replication of technical indicators calculations
from the feature-eng repository using pandas_ta library.
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class TechnicalIndicatorCalculator:
    """
    Technical indicator calculator that replicates the exact logic 
    from feature-eng/app/plugins/tech_indicator.py
    """
    
    # Default parameters matching feature-eng plugin
    DEFAULT_PARAMS = {
        'short_term_period': 14,
        'mid_term_period': 50,
        'long_term_period': 200,
        'indicators': ['rsi', 'macd', 'ema', 'stoch', 'adx', 'atr', 'cci', 'bbands', 'williams', 'momentum', 'roc'],
        'ohlc_order': 'ohlc'
    }
    
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """Initialize the technical indicator calculator."""
        self.params = self.DEFAULT_PARAMS.copy()
        if params:
            self.params.update(params)
    
    def calculate_all_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all technical indicators matching feature-eng exactly.
        
        Args:
            data: DataFrame with OHLC columns (OPEN, HIGH, LOW, CLOSE)
            
        Returns:
            DataFrame with calculated technical indicators
        """
        try:
            # Prepare OHLC data for pandas_ta
            ohlc_data = self._prepare_ohlc_data(data)
            
            # Calculate technical indicators
            indicators = {}
            
            for indicator in self.params['indicators']:
                indicator_results = self._calculate_indicator(indicator, ohlc_data)
                indicators.update(indicator_results)
            
            # Add additional features (price relationships)
            price_features = self._calculate_price_features(data)
            indicators.update(price_features)
            
            # Add seasonality features if datetime index available
            seasonality_features = self._calculate_seasonality_features(data)
            indicators.update(seasonality_features)
            
            # Create DataFrame from indicators
            indicator_df = pd.DataFrame(indicators, index=data.index)
            
            logger.info(f"Calculated {len(indicators)} technical indicators")
            return indicator_df
            
        except Exception as e:
            logger.error(f"Error calculating technical indicators: {e}")
            return pd.DataFrame(index=data.index)
    
    def _prepare_ohlc_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Prepare OHLC data for pandas_ta calculations."""
        ohlc_mapping = {
            'OPEN': 'Open',
            'HIGH': 'High', 
            'LOW': 'Low',
            'CLOSE': 'Close'
        }
        
        ohlc_data = data.copy()
        for old_name, new_name in ohlc_mapping.items():
            if old_name in ohlc_data.columns:
                ohlc_data[new_name] = ohlc_data[old_name]
        
        # Verify required columns exist
        required_cols = ['Open', 'High', 'Low', 'Close']
        for col in required_cols:
            if col not in ohlc_data.columns:
                raise ValueError(f"Missing required column: {col}")
        
        return ohlc_data
    
    def _calculate_indicator(self, indicator: str, ohlc_data: pd.DataFrame) -> Dict[str, pd.Series]:
        """Calculate a specific technical indicator."""
        try:
            import pandas_ta as ta
        except ImportError:
            logger.warning("pandas_ta not available, skipping technical indicators")
            return {}
        
        indicators = {}
        
        logger.debug(f"Calculating indicator: {indicator}")
        
        if indicator == 'rsi':
            rsi = ta.rsi(ohlc_data['Close'], length=self.params['short_term_period'])
            if rsi is not None:
                indicators['RSI'] = rsi
        
        elif indicator == 'macd':
            macd = ta.macd(ohlc_data['Close'])  # Default fast=12, slow=26, signal=9
            if macd is not None:
                if 'MACD_12_26_9' in macd.columns:
                    indicators['MACD'] = macd['MACD_12_26_9']
                if 'MACDh_12_26_9' in macd.columns:
                    indicators['MACD_Histogram'] = macd['MACDh_12_26_9']
                if 'MACDs_12_26_9' in macd.columns:
                    indicators['MACD_Signal'] = macd['MACDs_12_26_9']
        
        elif indicator == 'ema':
            ema = ta.ema(ohlc_data['Close'], length=20)  # Default length is 20
            if ema is not None:
                indicators['EMA'] = ema
        
        elif indicator == 'stoch':
            stoch = ta.stoch(ohlc_data['High'], ohlc_data['Low'], ohlc_data['Close'])
            if stoch is not None:
                if 'STOCHk_14_3_3' in stoch.columns:
                    indicators['Stochastic_%K'] = stoch['STOCHk_14_3_3']
                if 'STOCHd_14_3_3' in stoch.columns:
                    indicators['Stochastic_%D'] = stoch['STOCHd_14_3_3']
        
        elif indicator == 'adx':
            adx = ta.adx(ohlc_data['High'], ohlc_data['Low'], ohlc_data['Close'], length=self.params['short_term_period'])
            if adx is not None:
                if 'ADX_14' in adx.columns:
                    indicators['ADX'] = adx['ADX_14']
                if 'DMP_14' in adx.columns:
                    indicators['DI+'] = adx['DMP_14']
                if 'DMN_14' in adx.columns:
                    indicators['DI-'] = adx['DMN_14']
        
        elif indicator == 'atr':
            atr = ta.atr(ohlc_data['High'], ohlc_data['Low'], ohlc_data['Close'], length=self.params['short_term_period'])
            if atr is not None:
                indicators['ATR'] = atr
        
        elif indicator == 'cci':
            cci = ta.cci(ohlc_data['High'], ohlc_data['Low'], ohlc_data['Close'], length=20)
            if cci is not None:
                indicators['CCI'] = cci
        
        elif indicator == 'bbands':
            bbands = ta.bbands(ohlc_data['Close'], length=20, std=2.0)
            if bbands is not None:
                if 'BBU_20_2.0' in bbands.columns:
                    indicators['BB_Upper'] = bbands['BBU_20_2.0']
                if 'BBM_20_2.0' in bbands.columns:
                    indicators['BB_Middle'] = bbands['BBM_20_2.0']
                if 'BBL_20_2.0' in bbands.columns:
                    indicators['BB_Lower'] = bbands['BBL_20_2.0']
        
        elif indicator == 'williams':
            williams = ta.willr(ohlc_data['High'], ohlc_data['Low'], ohlc_data['Close'], length=self.params['short_term_period'])
            if williams is not None:
                indicators['WilliamsR'] = williams
        
        elif indicator == 'momentum':
            momentum = ta.mom(ohlc_data['Close'], length=10)
            if momentum is not None:
                indicators['Momentum'] = momentum
        
        elif indicator == 'roc':
            roc = ta.roc(ohlc_data['Close'], length=10)
            if roc is not None:
                indicators['ROC'] = roc
        
        return indicators
    
    def _calculate_price_features(self, data: pd.DataFrame) -> Dict[str, pd.Series]:
        """Calculate price relationship features."""
        features = {}
        
        # Price relationships (Bar Characteristics) - matching feature-eng
        if all(col in data.columns for col in ['HIGH', 'LOW']):
            features['BH-BL'] = data['HIGH'] - data['LOW']
        
        if all(col in data.columns for col in ['HIGH', 'OPEN']):
            features['BH-BO'] = data['HIGH'] - data['OPEN']
        
        if all(col in data.columns for col in ['OPEN', 'LOW']):
            features['BO-BL'] = data['OPEN'] - data['LOW']
        
        if all(col in data.columns for col in ['CLOSE', 'OPEN']):
            features['BC-BO'] = data['CLOSE'] - data['OPEN']
        
        return features
    
    def _calculate_seasonality_features(self, data: pd.DataFrame) -> Dict[str, pd.Series]:
        """Calculate seasonality features from datetime index."""
        features = {}
        
        # Check if we have datetime index or DATE_TIME column
        if hasattr(data.index, 'day'):
            features['day_of_month'] = data.index.day
            features['hour_of_day'] = data.index.hour  
            features['day_of_week'] = data.index.dayofweek
        elif 'DATE_TIME' in data.columns:
            dt_series = pd.to_datetime(data['DATE_TIME'])
            features['day_of_month'] = dt_series.dt.day
            features['hour_of_day'] = dt_series.dt.hour
            features['day_of_week'] = dt_series.dt.dayofweek
        
        return features
    
    def get_expected_columns(self) -> list:
        """Return list of expected technical indicator column names."""
        expected_columns = [
            'RSI', 'MACD', 'MACD_Histogram', 'MACD_Signal', 'EMA',
            'Stochastic_%K', 'Stochastic_%D', 'ADX', 'DI+', 'DI-',
            'ATR', 'CCI', 'WilliamsR', 'Momentum', 'ROC',
            'BH-BL', 'BH-BO', 'BO-BL', 'BC-BO',
            'day_of_month', 'hour_of_day', 'day_of_week'
        ]
        
        # Add Bollinger Bands if enabled
        if 'bbands' in self.params['indicators']:
            expected_columns.extend(['BB_Upper', 'BB_Middle', 'BB_Lower'])
        
        return expected_columns
