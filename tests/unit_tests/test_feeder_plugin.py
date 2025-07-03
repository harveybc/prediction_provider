"""
Unit tests for the DefaultFeederPlugin.
"""

import pytest
import pandas as pd
import numpy as np
import json
import os
from unittest.mock import patch, MagicMock

# This import assumes pandas_ta is installed in the environment
import pandas_ta as ta

from plugins_feeder.default_feeder import DefaultFeederPlugin

@pytest.fixture
def mock_config():
    """
    Provides a default mock configuration for the feeder.
    """
    # Create a dummy normalization file for the test
    norm_params = {
        "feature1": {"min": 0, "max": 10},
        "feature2": {"min": -5, "max": 5}
    }
    norm_path = "/tmp/test_norm.json"
    with open(norm_path, 'w') as f:
        json.dump(norm_params, f)

    return {
        "instrument": "EUR/USD",
        "n_batches": 1,
        "batch_size": 256,
        "use_normalization_json": norm_path,
        "required_columns": ["feature1", "feature2"] # Simplified for testing
    }

@pytest.fixture
def raw_data_df():
    """
    Provides a sample raw DataFrame that mocks the fetched data.
    """
    data = {
        'DATE_TIME': pd.to_datetime(pd.date_range(start="2025-01-01", periods=300, freq='h')),
        'Open': np.random.rand(300) * 10,
        'High': np.random.rand(300) * 10 + 5,
        'Low': np.random.rand(300) * 5,
        'Close': np.random.rand(300) * 10,
        'Volume': np.random.randint(1000, 5000, size=300)
    }
    df = pd.DataFrame(data)
    df.set_index('DATE_TIME', inplace=True)
    return df

def test_feeder_initialization(mock_config):
    """
    GIVEN a configuration dictionary
    WHEN a DefaultFeederPlugin is initialized
    THEN its parameters should be set correctly.
    """
    feeder = DefaultFeederPlugin(mock_config)
    assert feeder.params["instrument"] == "EUR/USD"
    assert feeder.params["batch_size"] == 256
    assert feeder.normalization_params is not None

@patch("plugins_feeder.default_feeder.DefaultFeederPlugin._fetch_instrument_data")
def test_feature_calculation(mock_fetch, mock_config, raw_data_df):
    """
    GIVEN a feeder with mocked raw data
    WHEN the _calculate_features method is called
    THEN it should add the technical indicator columns to the DataFrame.
    """
    mock_fetch.return_value = raw_data_df
    feeder = DefaultFeederPlugin(mock_config)

    # We are testing a private method here for isolation
    featured_df = feeder._calculate_features(raw_data_df)

    assert "RSI_14" in featured_df.columns
    assert "MACD_12_26_9" in featured_df.columns
    assert not featured_df["RSI_14"].isnull().all() # Check that calculation happened


def test_normalization(mock_config):
    """
    GIVEN a feeder with mock normalization parameters
    WHEN the _normalize_data method is called
    THEN the returned DataFrame's features should be normalized between 0 and 1.
    """
    # Let's create a more specific raw_df and norm_params for this test
    raw_data = {'feature1': np.array([0, 5, 10]), 'feature2': np.array([-5, 0, 5])}
    test_df = pd.DataFrame(raw_data)
    
    norm_params = {
        "feature1": {"min": 0, "max": 10},
        "feature2": {"min": -5, "max": 5}
    }
    norm_path = "/tmp/specific_norm.json"
    with open(norm_path, 'w') as f:
        json.dump(norm_params, f)

    mock_config["use_normalization_json"] = norm_path
    
    feeder = DefaultFeederPlugin(mock_config)

    normalized_df = feeder._normalize_data(test_df)

    assert np.allclose(normalized_df['feature1'], [0.0, 0.5, 1.0])
    assert np.allclose(normalized_df['feature2'], [0.0, 0.5, 1.0])

    # Clean up the dummy file
    os.remove(norm_path)

# Cleanup the dummy file
@pytest.fixture(scope="session", autouse=True)
def cleanup_files():
    """
    Cleanup created test files after the session.
    """
    yield
    if os.path.exists("/tmp/test_norm.json"):
        os.remove("/tmp/test_norm.json")
    if os.path.exists("/tmp/specific_norm.json"):
        os.remove("/tmp/specific_norm.json")
