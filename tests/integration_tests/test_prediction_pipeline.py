"""
Integration tests for the prediction pipeline.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch

from plugins_pipeline.default_pipeline import DefaultPipelinePlugin
from plugins_feeder.default_feeder import DefaultFeederPlugin
from plugins_predictor.default_predictor import DefaultPredictorPlugin

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
    feeder = MagicMock(spec=DefaultFeederPlugin)
    # Mock the data result that the feeder would return
    mock_df = pd.DataFrame(np.random.rand(256, 45), columns=[f'col{i}' for i in range(45)])
    feeder.fetch_data_for_prediction.return_value = {
        "data": mock_df,
        "metadata": {"source": "mock"}
    }
    return feeder

@pytest.fixture
def mock_predictor():
    """
    Creates a mock predictor plugin.
    """
    predictor = MagicMock(spec=DefaultPredictorPlugin)
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
    pipeline = DefaultPipelinePlugin(mock_config)
    pipeline.initialize(predictor_plugin=mock_predictor, feeder_plugin=mock_feeder)
    
    # To run the loop only once, we change the `running` flag after the first pass
    def stop_loop(*args, **kwargs):
        pipeline.running = False

    mock_predictor.predict_with_uncertainty.side_effect = stop_loop
    
    with patch.object(pipeline, '_store_prediction', wraps=pipeline._store_prediction) as spy_store_prediction:
        pipeline.run()
    
        # Verify the flow
        mock_feeder.fetch_data_for_prediction.assert_called_once()
        mock_predictor.predict_with_uncertainty.assert_called_once()
        # We can't easily assert the spy was called with the right data without more work,
        # but we can check it was called, which implies a successful cycle.
        assert spy_store_prediction.call_count == 1

    # Verify data was actually stored
    cursor = pipeline.db_conn.cursor()
    cursor.execute("SELECT * FROM predictions")
    rows = cursor.fetchall()
    assert len(rows) == 1
    assert rows[0][1] == "2025-07-02T12:00:00Z"
