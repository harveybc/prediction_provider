#!/usr/bin/env python3
"""
Plugin Loading Integration Tests

Tests the plugin loading and registration system to ensure all plugin types
can be loaded and initialized correctly.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from plugins_core.default_core import app

client = TestClient(app)

def test_core_plugin_loading():
    """
    Test Case 2.1: Verify that the core plugin is correctly loaded and functional.
    """
    # The fact that we can create a TestClient with the app instance
    # proves that the core plugin (FastAPI app) is loaded correctly
    assert app is not None
    
    # Test that basic app routes are available
    response = client.get("/health")
    assert response.status_code == 200

def test_all_plugin_types_loading():
    """
    Test Case 2.2: Ensure all plugin types can be instantiated.
    """
    # Test that we can import and instantiate all plugin types
    from plugins_feeder.default_feeder import DefaultFeeder
    from plugins_predictor.default_predictor import DefaultPredictor  
    from plugins_pipeline.default_pipeline import DefaultPipelinePlugin
    
    # Test instantiation
    feeder = DefaultFeeder()
    predictor = DefaultPredictor()
    pipeline = DefaultPipelinePlugin()
    
    # Verify they are proper instances
    assert isinstance(feeder, DefaultFeeder)
    assert isinstance(predictor, DefaultPredictor)
    assert isinstance(pipeline, DefaultPipelinePlugin)
    
    # Verify required methods exist
    assert hasattr(feeder, 'fetch')  # actual method name
    assert hasattr(predictor, 'predict')
    assert hasattr(pipeline, 'initialize')

class TestPluginLoadingUnitStyle:
    """
    Unit-style tests for plugin loading functionality using mocks.
    """
    
    @patch('plugins_core.default_core.app')
    def test_core_plugin_loading(self, mock_app):
        """
        Test Case 2.3: Mock-based test for core plugin loading.
        """
        # Arrange
        mock_app.return_value = MagicMock()
        
        # Act & Assert
        # The import itself tests the loading mechanism
        from plugins_core.default_core import DefaultCorePlugin
        core_plugin = DefaultCorePlugin(config={})
        
        assert core_plugin is not None
        assert hasattr(core_plugin, 'start')  # actual method name
    
    def test_all_plugin_types_loading(self):
        """
        Test Case 2.4: Verify plugin type loading with mocks.
        """
        # Test plugin discovery and loading patterns
        plugin_types = [
            ('plugins_feeder.default_feeder', 'DefaultFeeder'),
            ('plugins_predictor.default_predictor', 'DefaultPredictor'),
            ('plugins_pipeline.default_pipeline', 'DefaultPipelinePlugin')
        ]
        
        for module_name, class_name in plugin_types:
            # Test that modules can be imported
            module = __import__(module_name, fromlist=[class_name])
            plugin_class = getattr(module, class_name)
            
            # Test that classes can be instantiated
            plugin_instance = plugin_class()
            assert plugin_instance is not None
