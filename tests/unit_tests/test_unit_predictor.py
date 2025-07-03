import unittest
from unittest.mock import patch, MagicMock
import numpy as np

# Assuming the predictor plugin is in this path
from plugins_predictor.default_predictor import DefaultPredictor

class TestUnitPredictor(unittest.TestCase):
    """
    Unit tests for the DefaultPredictor plugin.
    
    These tests verify the predictor's internal logic, such as model path
    construction and data processing, without loading a real model.
    """

    def setUp(self):
        """Set up a fresh instance of the predictor for each test."""
        self.predictor = DefaultPredictor()
        # Mock the internal state that would be set by the framework
        self.predictor.model_dir = "plugins_predictor/models"

    def test_model_loader_logic(self):
        """
        Test Case 3.1: Verify the model path construction logic.
        """
        # Arrange
        model_name = "my_test_model"
        expected_path = "plugins_predictor/models/my_test_model.keras"

        # Act
        # Accessing a protected method for this unit test is acceptable.
        actual_path = self.predictor._get_model_path(model_name)

        # Assert
        self.assertEqual(actual_path, expected_path)

    @patch('tensorflow.keras.models.load_model')
    def test_prediction_with_mock_model(self, mock_load_model):
        """
        Test Case 3.2: Ensure the predict method processes data correctly
        using a mocked model.
        """
        # Arrange
        # Configure the mock model to return a predictable output
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([[0.5, 0.6]]) # Mocked prediction and uncertainty
        mock_load_model.return_value = mock_model

        # Create sample input data matching the expected 45 columns
        sample_input = np.random.rand(1, 128, 45) 

        # Act: Call the predict method
        result = self.predictor.predict("mock_model", sample_input)

        # Assert
        # Verify the model was loaded and its predict method was called
        mock_load_model.assert_called_once_with("plugins_predictor/models/mock_model.keras")
        mock_model.predict.assert_called_once()
        
        # Verify the output is correctly formatted
        self.assertIn("prediction", result)
        self.assertIn("uncertainty", result)
        self.assertEqual(result["prediction"], 0.5)
        self.assertEqual(result["uncertainty"], 0.6)

if __name__ == '__main__':
    unittest.main()

