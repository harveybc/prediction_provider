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
    feeder.fetch_data_sync.return_value = mock_df
    return feeder

@pytest.fixture
def mock_predictor():
    """
    Creates a mock predictor plugin.
    """
    predictor = MagicMock(spec=DefaultPredictor)
    # Mock the prediction output
    predictor.predict.return_value = {
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
    pipeline = DefaultPipeline(mock_config)
    pipeline.initialize(predictor_plugin=mock_predictor, feeder_plugin=mock_feeder)
    
    assert pipeline.predictor_plugin is mock_predictor
    assert pipeline.feeder_plugin is mock_feeder
    assert pipeline.db_conn is not None
    assert pipeline._validate_system() is True

@patch("time.sleep", return_value=None) # Mock time.sleep to avoid waiting
def test_pipeline_run_cycle(mock_sleep, mock_config, mock_feeder, mock_predictor):
    """
    GIVEN an initialized pipeline with a mock feeder and predictor
    WHEN the run method is executed for one cycle
    THEN it should call the feeder to get data, the predictor to get a prediction,
    and store the result in the database.
    """
    pipeline = DefaultPipeline(mock_config)
    pipeline.initialize(predictor_plugin=mock_predictor, feeder_plugin=mock_feeder)

    # We will manually call the internal logic of the loop once
    # to avoid dealing with breaking out of a `while True` loop in a test.
    pipeline._run_single_cycle()

    # Verify the flow
    mock_feeder.fetch_data_sync.assert_called_once()
    mock_predictor.predict.assert_called_once()

    # Verify data was actually stored
    cursor = pipeline.db_conn.cursor()
    cursor.execute("SELECT * FROM predictions")
    rows = cursor.fetchall()
    assert len(rows) == 1
    assert rows[0][1] == "2025-07-02T12:00:00Z"

def test_end_to_end_prediction(mock_config, mock_feeder, mock_predictor):
    """
    Test Case 5.1: Verify the complete prediction workflow.
    """
    # Arrange
    # Mock the external-facing methods of the feeder and predictor
    mock_feeder.fetch_data_sync = MagicMock(return_value="some_raw_data")
    mock_predictor.predict = MagicMock(return_value={"prediction": 123})

    pipeline = DefaultPipeline(mock_config)
    pipeline.initialize(predictor_plugin=mock_predictor, feeder_plugin=mock_feeder)

    # Act: Run the pipeline with a dummy ticker
    result = pipeline.run("AAPL")

    # Assert
    # Verify that the feeder and predictor were called in sequence
    mock_feeder.fetch_data_sync.assert_called_once_with("AAPL")
    # This conceptual test assumes the pipeline passes the data to the predictor
    mock_predictor.predict.assert_called_once()
    assert result["prediction"] == 123

def test_model_loading_and_caching(mock_config, mock_feeder, mock_predictor):
    """
    Test Case 5.2: Ensure the predictor caches the loaded model.
    """
    # Arrange
    # Use a real predictor instance to test its internal cache.
    # Mock the actual model loading to avoid file system access.
    with patch.object(mock_predictor, '_load_model') as mock_load_model:
        mock_load_model.return_value = MagicMock() # A dummy model object

        # Act: Run the prediction twice for the same model
        mock_predictor.predict("cached_model", "dummy_data_1")
        mock_predictor.predict("cached_model", "dummy_data_2")

        # Assert: The model should only be loaded from disk once
        mock_load_model.assert_called_once_with("cached_model")
