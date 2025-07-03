#!/usr/bin/env python3
"""
Default Core Plugin for Prediction Provider.

This plugin is the central orchestrator of the application. It handles:
- Loading and managing all other plugins (feeder, predictor, pipeline, endpoints).
- Initializing the system in the correct order.
- Starting and stopping the application services.
"""

import os
import importlib
import threading
from fastapi import FastAPI
import uvicorn

# The FastAPI app instance is created here, making it accessible for tests
app = FastAPI(
    title="Prediction Provider API",
    description="A robust, plugin-based, asynchronous prediction provider for financial time series.",
    version="0.1.0"
)

class PluginManager:
    """A simple manager to register and retrieve plugins by name."""
    def __init__(self):
        self._plugins = {}

    def register(self, plugin):
        """Registers a plugin instance."""
        if not hasattr(plugin, 'name'):
            # The test uses a mock with a .name attribute.
            # This check makes the class more robust.
            return
        self._plugins[plugin.name] = plugin

    def get(self, name):
        """Retrieves a plugin by its name."""
        return self._plugins.get(name)

class DefaultCorePlugin:
    """
    The central core plugin for the Prediction Provider application.
    This plugin is responsible for managing the FastAPI application lifecycle.
    """

    plugin_params = {
        "host": "127.0.0.1",
        "port": 8000,
    }

    plugin_debug_vars = ["host", "port"]

    def __init__(self, config):
        """
        Initializes the core plugin.

        Args:
            config (dict): The global application configuration.
        """
        self.params = self.plugin_params.copy()
        self.params.update(config)
        self.plugins = {}
        self.app = app  # Use the module-level app instance

    def set_params(self, **kwargs):
        """
        Updates the core parameters.
        """
        self.params.update(kwargs)

    def set_plugins(self, plugins: dict):
        """
        Receives all loaded plugins from the main orchestrator.
        It then registers the necessary components, like API endpoints.
        """
        self.plugins = plugins
        print("Core plugin received plugins:", list(self.plugins.keys()))
        
        endpoints_plugin = self.plugins.get('endpoints')
        if endpoints_plugin and hasattr(endpoints_plugin, 'register_routes'):
            print("Registering routes from endpoints plugin...")
            endpoints_plugin.register_routes(self.app)
        else:
            print("Warning: Endpoints plugin not found or it lacks a 'register_routes' method.")

    def start(self):
        """
        Starts the FastAPI application using uvicorn.
        """
        print(f"--- Starting FastAPI Server at http://{self.params['host']}:{self.params['port']} ---")
        try:
            uvicorn.run(
                self.app,
                host=self.params['host'],
                port=self.params['port']
            )
        except Exception as e:
            print(f"Error starting uvicorn server: {e}")

    def stop(self):
        """
        Stops the application. Uvicorn handles graceful shutdown.
        """
        print("--- Stopping Application ---")
        # This is a simplified stop mechanism. A more robust implementation
        # would involve signaling the threads to stop gracefully.
        if hasattr(self, 'pipeline_thread') and self.pipeline_thread.is_alive():
            # In a real-world scenario, you'd have a more graceful shutdown mechanism
            # For now, we rely on daemon threads
            pass

        print("--- Application Stopped ---")

    def _get_plugin_by_type(self, plugin_type):
        """
        Finds the first loaded plugin from a given directory prefix.
        """
        for name, plugin in self.plugins.items():
            if name.startswith(plugin_type):
                return plugin
        return None

# For backward compatibility
Plugin = DefaultCorePlugin
