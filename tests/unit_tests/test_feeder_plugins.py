import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

# Corrected import path
from plugins_feeder.default_feeder import DefaultFeeder

@pytest.fixture
def feeder():
    """Provides a DefaultFeeder instance for testing."""
    return DefaultFeeder()

@patch('plugins_feeder.default_feeder.yf.Ticker')
def test_feeder_fetch_data_successfully(mock_yf_ticker, feeder):
    """
    Tests the feeder's ability to retrieve and process data successfully.
    """
    # Create a mock DataFrame with proper OHLC structure
    mock_df = pd.DataFrame({
        'Open': [100, 102, 105],
        'High': [101, 103, 106],
        'Low': [99, 101, 104],
        'Close': [100, 102, 105],
        'Volume': [1000, 1100, 1200]
    }, index=pd.date_range('2025-06-30', periods=3, freq='h'))
    
    # Mock the ticker instance and its history method
    mock_ticker_instance = MagicMock()
    mock_ticker_instance.history.return_value = mock_df
    mock_yf_ticker.return_value = mock_ticker_instance

    # Execute the fetch method
    data = feeder.fetch()

    # Assert that yfinance Ticker was called
    mock_yf_ticker.assert_called()
    # Assert that data is returned
    assert data is not None
    assert isinstance(data, pd.DataFrame)

@patch('plugins_feeder.default_feeder.yf.Ticker')
def test_feeder_handles_different_parameters(mock_yf_ticker, feeder):
    """
    Tests that the feeder correctly handles different parameter configurations.
    """
    mock_df = pd.DataFrame({
        'Open': [102, 105],
        'High': [103, 106],
        'Low': [101, 104],
        'Close': [102, 105],
        'Volume': [1100, 1200]
    }, index=pd.date_range('2025-07-01', periods=2, freq='h'))
    
    # Mock the ticker instance and its history method
    mock_ticker_instance = MagicMock()
    mock_ticker_instance.history.return_value = mock_df
    mock_yf_ticker.return_value = mock_ticker_instance

    # Set different parameters
    feeder.set_params(instrument="AAPL", batch_size=128)

    data = feeder.fetch()

    mock_yf_ticker.assert_called()
    assert data is not None
    assert isinstance(data, pd.DataFrame)

@patch('plugins_feeder.default_feeder.yf.Ticker')
def test_feeder_handles_fetch_error(mock_yf_ticker, feeder):
    """
    Tests that the feeder plugin handles errors during data fetching gracefully.
    """
    # Mock yfinance to raise an exception
    mock_ticker_instance = MagicMock()
    mock_ticker_instance.history.side_effect = Exception("Network error")
    mock_yf_ticker.return_value = mock_ticker_instance
    
    with pytest.raises(Exception):
        feeder.fetch()
