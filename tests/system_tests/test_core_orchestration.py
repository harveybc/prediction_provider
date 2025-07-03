"""
System tests for the Prediction Provider core orchestration.
"""

import pytest
import os
from unittest.mock import MagicMock, patch

from plugins_core.default_core import DefaultCorePlugin
from plugins_pipeline.default_pipeline import DefaultPipelinePlugin
from plugins_feeder.default_feeder import DefaultFeederPlugin
from plugins_predictor.default_predictor import DefaultPredictorPlugin
from plugins_endpoints.default_endpoints import DefaultEndpointsPlugin

@pytest.fixture
def mock_config():
    """
    Provides a default mock configuration.
    """
    return {
        "plugin_directories": [
            "plugins_feeder",
            "plugins_predictor",
            "plugins_pipeline",
            "plugins_endpoints"
        ],
        "db_path": ":memory:" # Use in-memory DB for tests
    }

@patch("importlib.import_module")
def test_core_plugin_loads_all_plugins(mock_import_module, mock_config):
    """
    GIVEN a core plugin and mocked plugin modules
    WHEN load_plugins is called
    THEN it should discover and instantiate all plugin types.
    """
    # Mock the modules that would be discovered
    mock_feeder_module = MagicMock()
    mock_feeder_module.DefaultFeederPlugin = DefaultFeederPlugin
    
    mock_predictor_module = MagicMock()
    mock_predictor_module.DefaultPredictorPlugin = DefaultPredictorPlugin

    mock_pipeline_module = MagicMock()
    mock_pipeline_module.DefaultPipelinePlugin = DefaultPipelinePlugin

    mock_endpoints_module = MagicMock()
    mock_endpoints_module.DefaultEndpointsPlugin = DefaultEndpointsPlugin

    # Configure the mock to return the correct module based on the import path
    def import_side_effect(module_name):
        if "plugins_feeder.default_feeder" in module_name:
            return mock_feeder_module
        if "plugins_predictor.default_predictor" in module_name:
            return mock_predictor_module
        if "plugins_pipeline.default_pipeline" in module_name:
            return mock_pipeline_module
        if "plugins_endpoints.default_endpoints" in module_name:
            return mock_endpoints_module
        return MagicMock()

    mock_import_module.side_effect = import_side_effect

    # Mock os.listdir to return our dummy plugin files
    with patch("os.listdir") as mock_listdir:
        mock_listdir.return_value = ["default_feeder.py", "default_predictor.py", "default_pipeline.py", "default_endpoints.py"]
        
        core_plugin = DefaultCorePlugin(mock_config)
        core_plugin.load_plugins()
        
        assert len(core_plugin.plugins) == 4
        assert any(isinstance(p, DefaultFeederPlugin) for p in core_plugin.plugins.values())
        assert any(isinstance(p, DefaultPredictorPlugin) for p in core_plugin.plugins.values())
        assert any(isinstance(p, DefaultPipelinePlugin) for p in core_plugin.plugins.values())
        assert any(isinstance(p, DefaultEndpointsPlugin) for p in core_plugin.plugins.values())

@patch("plugins_core.default_core.DefaultCorePlugin.load_plugins")
@patch("threading.Thread")
def test_core_plugin_start_and_stop(mock_thread, mock_load_plugins, mock_config):
    """
    GIVEN a core plugin with mocked child plugins
    WHEN the start method is called
    THEN it should initialize the pipeline and start it in a new thread.
    AND WHEN the stop method is called
    THEN it should call the pipeline's stop method.
    """
    core_plugin = DefaultCorePlugin(mock_config)
    
    # Manually insert mock plugins
    mock_pipeline = MagicMock(spec=DefaultPipelinePlugin)
    mock_feeder = MagicMock(spec=DefaultFeederPlugin)
    mock_predictor = MagicMock(spec=DefaultPredictorPlugin)
    mock_endpoints = MagicMock(spec=DefaultEndpointsPlugin)

    core_plugin.plugins = {
        "plugins_pipeline_default_pipeline": mock_pipeline,
        "plugins_feeder_default_feeder": mock_feeder,
        "plugins_predictor_default_predictor": mock_predictor,
        "plugins_endpoints_default_endpoints": mock_endpoints
    }

    # Test start
    core_plugin.start()
    
    mock_pipeline.initialize.assert_called_once_with(predictor_plugin=mock_predictor, feeder_plugin=mock_feeder)
    mock_thread.assert_called_once_with(target=mock_pipeline.run, daemon=True)
    mock_thread.return_value.start.assert_called_once()
    mock_endpoints.initialize.assert_called_once_with(pipeline_plugin=mock_pipeline)
    mock_endpoints.run.assert_called_once()

    # Test stop
    core_plugin.stop()
    mock_pipeline.stop.assert_called_once()
