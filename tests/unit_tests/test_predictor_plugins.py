import pytest
from unittest.mock import patch, MagicMock
import numpy as np

# Corrected import path
from app.predictor_plugins.default_predictor import DefaultPredictor

@pytest.fixture
def predictor():
    """Provides a DefaultPredictor instance for testing."""
    return DefaultPredictor()

@patch('tensorflow.keras.models.load_model')
def test_load_model_successfully(mock_load_model, predictor):
    """
    Tests that the predictor can successfully load a model.
    The model type determines the file path.
    """
    # Mock the loaded model object
    mock_model = MagicMock()
    mock_load_model.return_value = mock_model

    # Test loading a 'long_term' model
    predictor.load_model("long_term")

    # Assert that the load_model function was called with the correct path
    expected_path_long_term = "models/predictor_model_long_term.h5"
    mock_load_model.assert_called_with(expected_path_long_term)
    assert predictor.model == mock_model

    # Test loading a 'short_term' model
    predictor.load_model("short_term")
    expected_path_short_term = "models/predictor_model_short_term.h5"
    mock_load_model.assert_called_with(expected_path_short_term)
    assert predictor.model == mock_model

def test_predict_with_loaded_model(predictor):
    """
    Tests the predict method, ensuring it calls the model's predict function
    and returns the prediction and uncertainty.
    """
    # Mock the model attribute of the predictor instance
    mock_model = MagicMock()
    # Configure the mock model's predict method to return a sample prediction
    mock_model.predict.return_value = np.array([[110]]) # Example output
    predictor.model = mock_model

    # Create sample input data (e.g., a numpy array)
    sample_data = np.random.rand(1, 128, 1) # Shape for short-term model

    # Execute the predict method
    prediction, uncertainty = predictor.predict(sample_data)

    # Assert that the model's predict method was called with the data
    mock_model.predict.assert_called_once_with(sample_data)

    # Assert that the results are in the expected format
    assert prediction is not None
    assert uncertainty is not None
    assert isinstance(prediction, float)
    assert prediction == 110.0

@patch('tensorflow.keras.models.load_model', side_effect=IOError("Model not found"))
def test_load_model_handles_file_not_found(mock_load_model, predictor):
    """
    Tests that the predictor raises an IOError when the model file
    does not exist at the specified path.
    """
    with pytest.raises(IOError):
        predictor.load_model("non_existent_model")

def test_predict_without_loading_model_raises_error(predictor):
    """
    Tests that calling predict before a model has been loaded
    raises an Exception.
    """
    with pytest.raises(Exception, match="Model has not been loaded yet."):
        predictor.predict(np.random.rand(1, 128, 1))
