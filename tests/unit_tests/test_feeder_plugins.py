import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

# Corrected import path
from plugins_feeder.default_feeder import DefaultFeeder

@pytest.fixture
def feeder():
    """Provides a DefaultFeeder instance for testing."""
    return DefaultFeeder()

@patch('pandas.read_csv')
def test_get_data_for_long_term_prediction(mock_read_csv, feeder):
    """
    Tests the feeder's ability to retrieve and process data for a
    long-term prediction, which requires a specific window size (288).
    """
    # Create a mock DataFrame
    mock_df = pd.DataFrame({
        'timestamp': pd.to_datetime(['2025-06-30', '2025-07-01', '2025-07-02']),
        'value': [100, 102, 105]
    })
    mock_read_csv.return_value = mock_df

    # Define request parameters
    request_params = {
        "datetime": "2025-07-02T00:00:00Z",
        "window_size": 288,
        "prediction_type": "long_term"
    }

    # Execute the get_data method
    data = feeder.get_data(**request_params)

    # Assert that pandas.read_csv was called (path might need adjustment)
    mock_read_csv.assert_called_once()

    # Assert that the returned data is not empty
    assert data is not None
    # Further assertions can be made about the shape or content of the data
    # For example, checking if the data is a numpy array or a pandas series
    # as expected by the predictor plugins.

@patch('pandas.read_csv')
def test_get_data_for_short_term_prediction(mock_read_csv, feeder):
    """
    Tests the feeder's ability to retrieve and process data for a
    short-term prediction with a window size of 128.
    """
    mock_df = pd.DataFrame({
        'timestamp': pd.to_datetime(['2025-07-01', '2025-07-02']),
        'value': [102, 105]
    })
    mock_read_csv.return_value = mock_df

    request_params = {
        "datetime": "2025-07-02T00:00:00Z",
        "window_size": 128,
        "prediction_type": "short_term"
    }

    data = feeder.get_data(**request_params)

    mock_read_csv.assert_called_once()
    assert data is not None

def test_feeder_handles_missing_data_file(feeder):
    """
    Tests that the feeder plugin raises a FileNotFoundError when the
    data source (e.g., a CSV file) is not available.
    """
    with patch('pandas.read_csv', side_effect=FileNotFoundError):
        with pytest.raises(FileNotFoundError):
            feeder.get_data(
                datetime="2025-07-02T00:00:00Z",
                window_size=128,
                prediction_type="short_term"
            )
