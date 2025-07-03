# This file will contain integration tests for the model selection pipeline.

import pytest
import pandas as pd
from unittest.mock import Mock, patch

# Corrected import paths
from plugins_pipeline.default_pipeline import DefaultPipelinePlugin
from plugins_feeder.default_feeder import DefaultFeeder
from plugins_predictor.default_predictor import DefaultPredictor

@pytest.fixture
def mock_plugins():
    """Fixture to provide mocked feeder and predictor plugins."""
    mock_feeder = Mock(spec=DefaultFeeder)
    mock_predictor = Mock(spec=DefaultPredictor)
    # Configure mock return values if necessary for the pipeline to run
    mock_feeder.fetch.return_value = pd.DataFrame({"Close": [100, 101, 102]})
    mock_predictor.predict.return_value = ([101.5, 102.5], [0.1, 0.2])
    return mock_feeder, mock_predictor

def test_model_selection_for_long_term_prediction(mock_plugins):
    """
    Tests if the pipeline correctly configures the feeder and predictor
    for parameter changes.
    """
    mock_feeder, mock_predictor = mock_plugins

    # Instantiate the pipeline with the mocked plugins
    pipeline = DefaultPipelinePlugin()
    with patch.object(pipeline, '_initialize_database'), \
         patch.object(pipeline, '_validate_system', return_value=True):
        pipeline.initialize(mock_predictor, mock_feeder)

    # Test that the pipeline can handle different parameters
    test_params = {
        "prediction_interval": 600,
        "enable_logging": True
    }
    
    # Act
    pipeline.set_params(**test_params)
    
    # Assert
    assert pipeline.params["prediction_interval"] == 600
    assert pipeline.params["enable_logging"] == True
    
    # Verify plugins are properly initialized
    assert pipeline.predictor_plugin == mock_predictor
    assert pipeline.feeder_plugin == mock_feeder

def test_model_selection_for_short_term_prediction(mock_plugins):
    """
    Tests if the pipeline correctly handles different configurations.
    """
    mock_feeder, mock_predictor = mock_plugins

    pipeline = DefaultPipelinePlugin()
    with patch.object(pipeline, '_initialize_database'), \
         patch.object(pipeline, '_validate_system', return_value=True):
        pipeline.initialize(mock_predictor, mock_feeder)

    # Test parameter configuration
    test_params = {
        "prediction_interval": 300,
        "log_level": "DEBUG"
    }
    
    pipeline.set_params(**test_params)

    # Assert parameters are set correctly
    assert pipeline.params["prediction_interval"] == 300
    assert pipeline.params["log_level"] == "DEBUG"
    
    # Verify system validation works
    assert pipeline._validate_system() == True
