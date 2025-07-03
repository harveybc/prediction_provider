"""
Unit tests for the DefaultPredictorPlugin.
"""

import pytest
import numpy as np
import json
import os
from unittest.mock import MagicMock, patch

from plugins_predictor.default_predictor import DefaultPredictorPlugin

@pytest.fixture
def mock_config():
    """
    Provides a default mock configuration for the predictor.
    """
    # Create a dummy normalization file for the test
    norm_params = {
        "close_price": {"mean": 100, "std": 10}
    }
    norm_path = "/tmp/pred_norm.json"
    with open(norm_path, 'w') as f:
        json.dump(norm_params, f)

    return {
        "model_path": "/tmp/dummy_model.keras",
        "normalization_params_path": norm_path,
        "prediction_target_column": "close_price",
        "mc_samples": 10
    }

@pytest.fixture
def mock_keras_model():
    """
    Creates a mock Keras model.
    """
    model = MagicMock()
    # Mock the prediction function to return a fixed value
    model.predict.return_value = np.array([[0.5]]) # Normalized prediction
    # Mock the call for uncertainty prediction
    model.return_value = np.array([[0.5]]) # For the `model(input, training=True)` call
    return model

@patch("tensorflow.keras.models.load_model")
def test_predictor_loading_and_predicting(mock_load_model, mock_config, mock_keras_model):
    """
    GIVEN a predictor and a mocked Keras model
    WHEN a model is loaded and predict_with_uncertainty is called
    THEN it should return a de-normalized prediction and uncertainty.
    """
    # Create a dummy model file
    with open(mock_config["model_path"], "w") as f:
        f.write("dummy model content")

    mock_load_model.return_value = mock_keras_model
    
    predictor = DefaultPredictorPlugin(mock_config)
    assert predictor.load_model()
    assert predictor.model is not None
    assert predictor.normalization_params is not None

    # Create dummy input data
    input_data = np.random.rand(1, 256, 44)
    
    result = predictor.predict_with_uncertainty(input_data)

    # Check the output structure
    assert "prediction" in result
    assert "uncertainty" in result
    assert "metadata" in result
    assert result["metadata"]["de_normalized"] is True

    # Check the de-normalization
    # Original prediction was 0.5. De-normalized should be (0.5 * std) + mean = (0.5 * 10) + 100 = 105
    assert np.isclose(result["prediction"][0][0], 105.0)

    # Cleanup the dummy file
    os.remove(mock_config["model_path"])
    os.remove(mock_config["normalization_params_path"])

def test_denormalization_logic(mock_config):
    """
    GIVEN a predictor with loaded normalization parameters
    WHEN the _denormalize private method is called
    THEN it should correctly apply the mean and std to the inputs.
    """
    predictor = DefaultPredictorPlugin(mock_config)
    predictor._load_normalization_params() # Manually load for this unit test

    predictions = np.array([0.5, 1.0, -0.5])
    uncertainties = np.array([0.1, 0.2, 0.1])

    denorm_preds, denorm_uncerts = predictor._denormalize(predictions, uncertainties)

    # Expected preds: (value * std) + mean
    expected_preds = np.array([(0.5*10)+100, (1.0*10)+100, (-0.5*10)+100])
    # Expected uncerts: value * std
    expected_uncerts = np.array([0.1*10, 0.2*10, 0.1*10])

    assert np.allclose(denorm_preds, expected_preds)
    assert np.allclose(denorm_uncerts, expected_uncerts)

    # Cleanup the dummy file
    os.remove(mock_config["normalization_params_path"])
