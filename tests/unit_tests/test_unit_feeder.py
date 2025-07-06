import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pkg_resources")

import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import yfinance as yf

# Assuming the feeder plugin is in this path
from plugins_feeder.default_feeder import DefaultFeeder

class TestUnitFeeder(unittest.TestCase):
    """
    Unit tests for the DefaultFeeder plugin.
    
    These tests verify the feeder's logic in isolation, particularly its
    ability to handle data fetching and process API responses correctly.
    External dependencies, like the yfinance API, are mocked.
    """

    def setUp(self):
        """Set up a fresh instance of the feeder for each test."""
        self.feeder = DefaultFeeder()

    @patch('yfinance.download')
    def test_fetch_data_success(self, mock_yf_download):
        """
        Test successful data fetching when the external API returns valid data.
        """
        # Arrange: Configure the mock to return a sample DataFrame
        sample_data = pd.DataFrame({
            'Open': [150.0], 'High': [152.5], 'Low': [149.0],
            'Close': [152.0], 'Volume': [1000000]
        }, index=pd.to_datetime(['2025-07-01']))
        mock_yf_download.return_value = sample_data

        # Act: Call the method under test
        result = self.feeder.fetch_data_sync("AAPL", "2025-07-01", "2025-07-01")

        # Assert: Verify the mock was called and the result is correct
        mock_yf_download.assert_called_once_with(
            "AAPL", start="2025-07-01", end="2025-07-01"
        )
        self.assertIsNotNone(result)
        self.assertFalse(result.empty)
        pd.testing.assert_frame_equal(result, sample_data)

    @patch('yfinance.download')
    def test_fetch_data_api_error(self, mock_yf_download):
        """
        Test the feeder's behavior when the external API raises an exception.
        """
        # Arrange: Configure the mock to simulate an API error
        mock_yf_download.side_effect = Exception("API is down")

        # Act & Assert: Verify that the feeder handles the exception gracefully
        with self.assertRaises(Exception) as context:
            self.feeder.fetch_data_sync("FAIL", "2025-01-01", "2025-01-02")
        
        self.assertTrue("API is down" in str(context.exception))

    @patch('yfinance.download')
    def test_fetch_data_empty_dataframe(self, mock_yf_download):
        """
        Test the feeder's behavior when the API returns an empty DataFrame.
        """
        # Arrange: Configure the mock to return an empty DataFrame
        mock_yf_download.return_value = pd.DataFrame()

        # Act: Call the method under test
        result = self.feeder.fetch_data_sync("EMPTY", "2025-01-01", "2025-01-02")

        # Assert: Verify the result is an empty DataFrame
        self.assertIsNotNone(result)
        self.assertTrue(result.empty)

if __name__ == '__main__':
    unittest.main()
