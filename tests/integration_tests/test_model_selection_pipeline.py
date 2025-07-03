# This file will contain integration tests for the model selection pipeline.

import pytest
from unittest.mock import Mock, patch

# Corrected import paths using app prefix
from app.pipeline_plugins.default_pipeline import DefaultPipeline
from app.feeder_plugins.default_feeder import DefaultFeeder
from app.predictor_plugins.default_predictor import DefaultPredictor

@pytest.fixture
def mock_plugins():
    """Fixture to provide mocked feeder and predictor plugins."""
    mock_feeder = Mock(spec=DefaultFeeder)
    mock_predictor = Mock(spec=DefaultPredictor)
    # Configure mock return values if necessary for the pipeline to run
    mock_feeder.get_data.return_value = "mock_data"
    mock_predictor.predict.return_value = ("mock_prediction", "mock_uncertainty")
    return mock_feeder, mock_predictor

def test_model_selection_for_long_term_prediction(mock_plugins):
    """
    Tests if the pipeline correctly configures the feeder and predictor
    for a 'long_term' prediction request.
    """
    mock_feeder, mock_predictor = mock_plugins

    # Instantiate the pipeline with the mocked plugins
    pipeline = DefaultPipeline(feeder=mock_feeder, predictor=mock_predictor)

    # Define the request parameters for a long-term prediction
    request_params = {
        "prediction_type": "long_term",
        "datetime": "2025-07-04T12:00:00Z"
        # Other params as required by the pipeline's run method
    }

    # Execute the pipeline
    pipeline.run(request_params)

    # 1. Assert feeder was called correctly
    # According to REFERENCE.md, long-term predictions use a window_size of 288.
    mock_feeder.get_data.assert_called_once_with(
        datetime=request_params["datetime"],
        window_size=288,
        prediction_type="long_term"
    )

    # 2. Assert predictor was configured and used correctly
    # It should be instructed to load the 'long_term' model.
    mock_predictor.load_model.assert_called_once_with("long_term")
    mock_predictor.predict.assert_called_once_with("mock_data")

def test_model_selection_for_short_term_prediction(mock_plugins):
    """
    Tests if the pipeline correctly configures the feeder and predictor
    for a 'short_term' prediction request.
    """
    mock_feeder, mock_predictor = mock_plugins

    pipeline = DefaultPipeline(feeder=mock_feeder, predictor=mock_predictor)

    request_params = {
        "prediction_type": "short_term",
        "datetime": "2025-07-04T12:00:00Z"
    }

    pipeline.run(request_params)

    # Assert feeder was called with short-term window_size (128)
    mock_feeder.get_data.assert_called_once_with(
        datetime=request_params["datetime"],
        window_size=128,
        prediction_type="short_term"
    )

    # Assert predictor was instructed to load the 'short_term' model
    mock_predictor.load_model.assert_called_once_with("short_term")
    mock_predictor.predict.assert_called_once_with("mock_data")
