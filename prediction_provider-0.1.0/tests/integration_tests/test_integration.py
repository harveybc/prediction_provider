
import pytest
from unittest.mock import patch, MagicMock

from app.plugin_loader import get_plugin
from app.pipeline_plugins.default_pipeline import DefaultPipeline
from app.predictor_plugins.predictor_plugin_base import PredictorPluginBase

@pytest.mark.integration
def test_plugin_loading_and_execution():
    """
    Feature: Correctly load and execute a plugin.
    Scenario: The system needs to load a specific predictor plugin and use it.
    Given: A valid plugin name and type.
    When: `get_plugin` is called.
    Then: The correct plugin instance should be returned and its methods should be executable.
    """
    # Test loading a known pipeline plugin
    pipeline_plugin = get_plugin("pipeline_plugins", "default_pipeline")
    assert isinstance(pipeline_plugin, DefaultPipeline)

    # Test loading a predictor plugin (mocking the actual class)
    with patch('importlib.import_module') as mock_import:
        mock_module = MagicMock()
        MockPredictor = MagicMock(spec=PredictorPluginBase)
        mock_module.TestPredictor = MockPredictor
        mock_import.return_value = mock_module

        predictor_plugin = get_plugin("predictor_plugins", "test_predictor")
        assert predictor_plugin is MockPredictor

@pytest.mark.integration
@patch('app.data_handler.fetch_data')
def test_pipeline_and_predictor_integration(fetch_data_mock):
    """
    Feature: A data processing pipeline integrates with a predictor plugin.
    Scenario: A pipeline fetches data, processes it, and passes it to a predictor.
    Given: A pipeline and a predictor plugin.
    When: The pipeline is executed with a prediction request.
    Then: The predictor's `predict` method should be called with the processed data.
    """
    fetch_data_mock.return_value = [1, 2, 3, 4, 5] # Dummy data

    mock_predictor = MagicMock(spec=PredictorPluginBase)
    mock_predictor.predict.return_value = ([0.1], [0.01])

    pipeline = DefaultPipeline()
    result = pipeline.execute({}, mock_predictor) # Empty params for simplicity

    fetch_data_mock.assert_called_once()
    mock_predictor.predict.assert_called_once_with([1, 2, 3, 4, 5])
    assert result == ([0.1], [0.01])

