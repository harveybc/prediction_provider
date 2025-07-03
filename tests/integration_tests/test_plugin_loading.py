import pytest
from fastapi.testclient import TestClient
from app.main import app  # Assuming your FastAPI app instance is in app.main

client = TestClient(app)

def test_core_plugin_loading():
    # This test will implicitly be covered by the app fixture loading,
    # but we can add an explicit check.
    # A more robust check would involve a custom app factory fixture
    # that allows inspecting the app state after startup.
    response = client.get("/health")
    assert response.status_code == 200
    # If the health check endpoint (from DefaultEndpoints) works,
    # it implies the DefaultCore and plugin system loaded.

def test_all_plugin_types_loading():
    # Similar to the core plugin test, this is implicitly tested.
    # We can check for a signature of each default plugin.
    # For example, the /health endpoint comes from DefaultEndpoints.
    assert client.get("/health").status_code == 200

    # A dummy request to predict implies Feeder, Pipeline, and Predictor loaded.
    # This will fail if the full pipeline isn't ready, so we expect a 500
    # if the database isn't set up, but not a 404.
    response = client.post("/predict", json={"ticker": "FAKE"})
    assert response.status_code != 404


import unittest
from unittest.mock import patch

# Assuming the App and PluginLoader are in these paths
from app.main import App, PluginLoader

class TestPluginLoading(unittest.TestCase):
    """
    Integration tests for the plugin loading system.
    
    These tests verify that the application can correctly discover,
    load, and register all types of plugins.
    """

    @patch.object(PluginLoader, 'load_plugins')
    def test_core_plugin_loading(self, mock_load_plugins):
        """
        Test Case 2.1: Verify that the core plugin is loaded.
        """
        # Arrange: Configure the mock to return a dummy core plugin
        mock_load_plugins.return_value = {
            "core": ["DefaultCore"], # Using strings for simplicity
            "feeder": [], "predictor": [], "pipeline": [], "endpoints": []
        }

        # Act: Initialize the App, which triggers plugin loading
        app_instance = App()

        # Assert
        mock_load_plugins.assert_called_once()
        self.assertIn("DefaultCore", app_instance.plugins["core"])

    @patch.object(PluginLoader, 'load_plugins')
    def test_all_plugin_types_loading(self, mock_load_plugins):
        """
        Test Case 2.2: Ensure at least one of each plugin type is loaded.
        """
        # Arrange: Configure the mock to return one of each plugin type
        mock_load_plugins.return_value = {
            "core": ["DefaultCore"],
            "feeder": ["DefaultFeeder"],
            "predictor": ["DefaultPredictor"],
            "pipeline": ["DefaultPipeline"],
            "endpoints": ["DefaultEndpoints"]
        }

        # Act
        app_instance = App()

        # Assert
        mock_load_plugins.assert_called_once()
        self.assertTrue(all(p in app_instance.plugins for p in ["core", "feeder", "predictor", "pipeline", "endpoints"]))
        self.assertEqual(len(app_instance.plugins["feeder"]), 1)
        self.assertEqual(len(app_instance.plugins["predictor"]), 1)

if __name__ == '__main__':
    unittest.main()
