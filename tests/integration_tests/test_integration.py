
#!/usr/bin/env python3
"""
Integration tests for plugin loading and basic system functionality.
"""

import pytest
from unittest.mock import patch, MagicMock

from plugins_pipeline.default_pipeline import DefaultPipelinePlugin
from plugins_predictor.default_predictor import DefaultPredictor
from plugins_feeder.default_feeder import DefaultFeeder

@pytest.mark.integration
def test_plugin_loading_and_execution():
    """
    Feature: Correctly load and execute plugins.
    Scenario: The system needs to load specific plugins and use them.
    Given: Valid plugin classes.
    When: Plugins are instantiated.
    Then: The correct plugin instances should be created and their methods should be executable.
    """
    # Test that plugins can be instantiated
    pipeline_plugin = DefaultPipelinePlugin()
    predictor_plugin = DefaultPredictor()
    feeder_plugin = DefaultFeeder()
    
    assert isinstance(pipeline_plugin, DefaultPipelinePlugin)
    assert isinstance(predictor_plugin, DefaultPredictor)
    assert isinstance(feeder_plugin, DefaultFeeder)
    
    # Test that plugins have required methods
    assert hasattr(pipeline_plugin, 'initialize')
    assert hasattr(predictor_plugin, 'predict')
    assert hasattr(feeder_plugin, 'fetch_data_sync')

@pytest.mark.integration
def test_pipeline_and_predictor_integration():
    """
    Feature: A data processing pipeline integrates with a predictor plugin.
    Scenario: A pipeline coordinates with feeder and predictor plugins.
    Given: A pipeline, feeder, and predictor plugin.
    When: The pipeline is initialized with plugins.
    Then: The pipeline should correctly manage the plugins.
    """
    # Create plugin instances
    pipeline = DefaultPipelinePlugin()
    predictor = DefaultPredictor()
    feeder = DefaultFeeder()
    
    # Test plugin initialization in pipeline
    with patch.object(pipeline, '_initialize_database'), \
         patch.object(pipeline, '_validate_system', return_value=True):
        
        pipeline.initialize(predictor, feeder)
        
        assert pipeline.predictor_plugin == predictor
        assert pipeline.feeder_plugin == feeder

