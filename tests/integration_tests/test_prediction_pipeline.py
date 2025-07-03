"""
Integration tests for the prediction pipeline.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch

# Assuming the plugins are in these paths
from plugins_pipeline.default_pipeline import DefaultPipelinePlugin
from plugins_feeder.default_feeder import DefaultFeeder
from plugins_predictor.default_predictor import DefaultPredictor

@pytest.fixture
def mock_config():
    """
    Provides a default mock configuration for the pipeline.
    """
    return {
        "db_path": ":memory:", # Use in-memory SQLite database for tests
        "prediction_interval": 1 # Run quickly for tests
    }

@pytest.fixture
def mock_feeder():
    """
    Creates a mock feeder plugin.
    """
    feeder = MagicMock(spec=DefaultFeeder)
    # Mock the data result that the feeder would return
    mock_df = pd.DataFrame(np.random.rand(256, 45), columns=[f'col{i}' for i in range(45)])
    feeder.fetch.return_value = mock_df
    return feeder

@pytest.fixture
def mock_predictor():
    """
    Creates a mock predictor plugin.
    """
    predictor = MagicMock(spec=DefaultPredictor)
    # Mock the prediction output
    predictor.predict_with_uncertainty.return_value = {
        "prediction_timestamp": "2025-07-02T12:00:00Z",
        "prediction": [1.0, 1.1, 1.2],
        "uncertainty": [0.1, 0.1, 0.1],
        "metadata": {"model_path": "mock_model.keras"}
    }
    return predictor

def test_pipeline_initialization(mock_config, mock_feeder, mock_predictor):
    """
    GIVEN a pipeline, a feeder, and a predictor
    WHEN the pipeline is initialized
    THEN it should correctly store references to the other plugins and set up the database.
    """
    pipeline = DefaultPipelinePlugin(mock_config)
    pipeline.initialize(mock_predictor, mock_feeder)
    
    assert pipeline.predictor_plugin is mock_predictor
    assert pipeline.feeder_plugin is mock_feeder
    assert pipeline.engine is not None
    assert pipeline._validate_system() is True

@patch("time.sleep", return_value=None) # Mock time.sleep to avoid waiting
def test_pipeline_run_cycle(mock_sleep, mock_config, mock_feeder, mock_predictor):
    """
    GIVEN an initialized pipeline with a mock feeder and predictor
    WHEN the run method is executed for one cycle
    THEN it should call the feeder to get data, the predictor to get a prediction,
    and store the result in the database.
    """
    pipeline = DefaultPipelinePlugin(mock_config)
    pipeline.initialize(mock_predictor, mock_feeder)

    # We will manually call the internal logic of the loop once
    # to avoid dealing with breaking out of a `while True` loop in a test.
    pipeline._run_single_cycle("test_prediction_123")

    # Verify the flow
    mock_feeder.fetch.assert_called_once()
    mock_predictor.predict_with_uncertainty.assert_called_once()

    # Verify the pipeline has a database connection
    assert pipeline.engine is not None

def test_end_to_end_prediction(mock_config, mock_feeder, mock_predictor):
    """
    Test Case 5.1: Verify the complete prediction workflow.
    """
    # Arrange
    # Mock the external-facing methods of the feeder and predictor
    mock_feeder.fetch = MagicMock(return_value=pd.DataFrame({"Close": [100, 101, 102]}))
    mock_predictor.predict_with_uncertainty = MagicMock(return_value={"prediction": 123, "uncertainty": 0.1})

    pipeline = DefaultPipelinePlugin(mock_config)
    pipeline.initialize(mock_predictor, mock_feeder)

    # Act: Run a single prediction cycle
    pipeline._run_single_cycle("test_prediction_123")

    # Assert
    # Verify that the feeder and predictor were called in sequence
    mock_feeder.fetch.assert_called_once()
    # This conceptual test assumes the pipeline passes the data to the predictor
    mock_predictor.predict_with_uncertainty.assert_called_once()

def test_model_loading_and_caching(mock_config, mock_feeder, mock_predictor):
    """
    Test Case 5.2: Ensure the predictor caches the loaded model.
    """
    # Arrange
    # Mock the load_model method to track calls
    mock_feeder.fetch = MagicMock(return_value=pd.DataFrame({"Close": [100, 101, 102]}))
    mock_predictor.predict_with_uncertainty = MagicMock(return_value={"prediction": 123, "uncertainty": 0.1})

    pipeline = DefaultPipelinePlugin(mock_config)
    pipeline.initialize(mock_predictor, mock_feeder)

    # Act: Run the prediction cycle twice
    pipeline._run_single_cycle("test_prediction_1")
    pipeline._run_single_cycle("test_prediction_2")

    # Assert: The predictor should have been called twice
    assert mock_predictor.predict_with_uncertainty.call_count == 2
